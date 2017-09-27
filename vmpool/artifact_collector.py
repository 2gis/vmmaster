# coding: utf-8

import os
import json
import time
import logging
import websocket

from threading import Thread
from collections import defaultdict
from multiprocessing.pool import ThreadPool

from core import utils
from core.config import config
from core.utils import wait_for
from core.video import VNCVideoHelper


log = logging.getLogger(__name__)


def run_script(script, host):
    """
    :param script: str
    :param host: str
    :return: status, headers, body
    """
    status_code = 200

    def on_open(_ws):
        def run():
            _ws.send(script)
            log.info('RunScript: Open websocket and send message %s '
                     'to vmmaster-agent on vm %s' % (script, host))
        _t = Thread(target=run)
        _t.daemon = True
        _t.start()

    def on_message(_ws, message):
        _ws.output += message

    def on_close(_ws):
        log.info("RunScript: Close websocket on vm %s" % host)

    def on_error(_ws, message):
        global status_code
        status_code = 500
        _ws.status = 1
        _ws.output += str(message)
        log.debug("RunScript error: %s" % message)

    ws = websocket.WebSocketApp(host,
                                on_message=on_message,
                                on_close=on_close,
                                on_open=on_open,
                                on_error=on_error)
    ws.output = ""
    ws.status = 0

    t = Thread(target=ws.run_forever)
    t.daemon = True
    t.start()

    while t.isAlive():
        yield None, None, None

    full_msg = json.dumps({"status": ws.status, "output": ws.output})
    ws.close()
    yield status_code, {}, full_msg


def save_artifact(session, filename, original_path):
    """
    :param session: Session
    :param filename: str
    :param original_path: str
    :return: str
    """
    new_path = ""

    for code, headers, body in get_artifact_from_endpoint(session.endpoint, original_path):
        pass

    if code == 200:
        path = os.sep.join(
            [config.SCREENSHOTS_DIR, str(session.id), "{}.log".format(filename)]
        )
        try:
            body = json.loads(body)
            utils.write_file(path, body.get("output", "no data"))
            new_path = path
            log.info("session {}: file {} was saved to {} ".format(session.id, filename, new_path))
        except:
            log.exception("session {}: selenium log file {} doesn't created".format(session.id, filename))

    else:
        log.error('session {}: cannot get artifact {} from endpoint'.format(
            session.id, original_path, session.endpoint)
        )

    return new_path


def get_artifact_from_endpoint(endpoint, path):
    """
    :param endpoint: Clone
    :param path: str
    :return: status, headers, body
    """
    host = "ws://{}/runScript".format(endpoint.agent_ws_url)
    script = '{"command": "sudo -S sh", "script": "cat %s"}' % path
    log.debug("Run script for {}, cmd={}".format(endpoint, script))
    for status, headers, body in run_script(script, host):
        yield None, None, None

    yield status, headers, body


def save_selenium_log(app, session_id, filename, original_path):
    with app.app_context():
        session = app.sessions.get_session(session_id, maybe_closed=True)
        if not session:
            log.error("Session %s not found and selenium log doesn't saved" % session.id)
            return

        try:
            log_path = save_artifact(session, filename, original_path)
            if log_path:
                session.selenium_log = log_path
                session.save()
                log.info("Selenium log saved to %s for session %s" % (log_path, session.id))
            else:
                log.warning("Selenium log doesn't saved for session %s" % session.id)
        except:
            log.exception("Error saving selenium log for session {} ({}: {})".format(
                session.id, "selenium_server", "/var/log/selenium_server.log")
            )


def screencast_recording(app, session_id):
    with app.app_context():
        session = app.sessions.get_session(session_id)
        if not session:
            log.error("session {}: session not found".format(session_id))
            return

        log.info("session {}: screencast starting".format(session_id))
        vnc_helper = VNCVideoHelper(
            session.endpoint.ip, filename_prefix=session.id, port=session.endpoint.vnc_port
        )
        vnc_helper.start_recording()

        def session_was_closed():
            _session = app.database.get_session(session_id)
            if _session and _session.closed:
                session.refresh()
                vnc_helper.stop()
                if not _session.take_screencast and "succeed" in _session.status:
                    vnc_helper.delete_source_video()
                return True

        wait_for(
            session_was_closed,
            timeout=getattr(config, "SCREENCAST_RECORDER_MAX_DURATION", 1800),
            sleep_time=3
        )
        vnc_helper.stop()
        log.info("session {}: screencast stopped".format(session_id))


class ArtifactCollector(ThreadPool):
    def __init__(self):
        super(ArtifactCollector, self).__init__(processes=getattr(config, "ENDPOINT_THREADPOOL_PROCESSES", 5))
        self.in_queue = defaultdict(list)
        log.info("ArtifactCollector started")

    def __reduce__(self):
        super(ArtifactCollector, self).__reduce__()

    def get_queue(self):
        res = {}
        for key in self.in_queue.keys():
            res['session {}'.format(key)] = len(self.in_queue[key])
        return res

    def add_task(self, session_id, method, *args, **kwargs):
        apply_result = self.apply_async(
            method, args=args, kwds=kwargs, callback=lambda r: self.on_task_complete(r, method.__name__, session_id)
        )
        self.in_queue[session_id].append(apply_result)
        log.info("session {}: task {} added to queue".format(session_id, method.__name__,))
        return True

    def on_task_complete(self, result, method_name, session_id):
        """
        :param result: str
        :param method_name: str
        :param session_id: int
        """
        self.in_queue.pop(session_id, None)
        log.debug("session {}: task {} completed with return value '{}'".format(session_id, method_name, result))

    def del_tasks_for_session(self, session_id):
        """
        :param session_id: int
        """
        for task in self.in_queue[session_id]:
            if task and not task.ready():
                task.successful()
                log.warning("session {}: aborting task {}".format(session_id, str(task)))
        try:
            del self.in_queue[session_id]
        except KeyError:
            log.exception("session {}: tasks already deleted from queue".format(session_id))

    def del_tasks(self, sessions_ids):
        """
        :param sessions_ids: list
        """
        for session_id in sessions_ids:
            self.del_tasks_for_session(session_id)

    def wait_for_complete(self, session_id):
        """
        :param session_id: int
        """
        start = time.time()
        timeout = getattr(config, "COLLECT_ARTIFACTS_WAIT_TIMEOUT", 60)

        while session_id in self.in_queue.keys():
            log.info("session {}: wait for tasks to complete: {}".format(
                session_id, self.in_queue[session_id]
            ))
            if time.time() - start > timeout:
                log.warning("session {}: timeout {} while waiting for tasks".format(session_id, timeout))
                self.del_tasks_for_session(session_id)
                break
            time.sleep(1)

        log.info("session {}: all tasks completed".format(session_id))

    def stop(self):
        self.del_tasks(self.in_queue.keys())
        self.close()
        log.info("ArtifactCollector stopped")

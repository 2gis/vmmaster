# coding: utf-8

import os
import json
import time
import logging
import websocket

from threading import Thread  # TODO: stop using threading.Thread, replace with twisted.reactor.callInThread
from collections import defaultdict
from multiprocessing.pool import ThreadPool as ProcessPool

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


class Task(object):
    def __init__(self, name, apply_result):
        self.name = name
        self.apply_result = apply_result

    def __str__(self):
        return self.name


class ArtifactCollector(ProcessPool):
    def __init__(self, database):
        super(ArtifactCollector, self).__init__(processes=getattr(config, "ENDPOINT_THREADPOOL_PROCESSES", 5))
        self.db = database
        self.in_queue = defaultdict(list)
        log.info("ArtifactCollector started")

    def __reduce__(self):
        super(ArtifactCollector, self).__reduce__()

    def _save_selenium_log(self, session, filename, original_path):
        try:
            log_path = save_artifact(session, filename, original_path)
            if log_path:
                session.selenium_log = log_path
                self.db.update(session)
                log.info("session {}: selenium log saved to {}".format(session.id, log_path))
            else:
                log.warning("session {}: selenium log doesn't saved".format(session.id))
        except:
            log.exception("session {}: error saving selenium log".format(session.id))

    def _screencast_recording(self, session):
        def is_recording_over():
            """
            Checks when task screencast_recording must be stopped: session closed or recorder is dead
            :return: boolean
            """
            if not vnc_helper.is_alive():
                log.warning('session {}: recorder is dead, finishing'.format(session.id))
                return True

            self.db.refresh(session)
            if session.closed:
                return True

            return False

        log.info("session {}: screencast starting".format(session.id))
        try:
            vnc_helper = VNCVideoHelper(
                session.endpoint.ip, filename_prefix=session.id, port=session.endpoint.vnc_port
            )
            vnc_helper.start_recording()
        except:
            log.exception("session {}: error starting VNCHelper".format(session.id))
            return

        wait_for(
            is_recording_over,
            timeout=getattr(config, "SCREENCAST_RECORDER_MAX_DURATION", 1800),
            sleep_time=3
        )
        try:
            vnc_helper.stop()
        except:
            log.exception("session {}: error stopping VNCHelper".format(session.id))
        else:
            log.info("session {}: screencast stopped".format(session.id))

        if not session.take_screencast and session.is_succeed:
            vnc_helper.delete_source_video()

    def record_screencast(self, session):
        # FIXME: ApplyAsync Video Recorder may start too late. Start VideoRecording synchronously
        return self.add_task(
            session.id, self._screencast_recording, session
        )

    def save_selenium_log(self, session):
        return self.add_task(
            session.id, self._save_selenium_log, *(
                session, "selenium_server", "/var/log/selenium_server.log"
            )
        )

    def get_queue(self):
        res = {}
        for key in self.in_queue.keys():
            res['session {}'.format(key)] = [task.name for task in self.in_queue[key]]
        return res

    def add_task(self, session_id, method, *args, **kwargs):
        apply_result = self.apply_async(
            method, args=args, kwds=kwargs, callback=lambda r: self.on_task_complete(r, method.__name__, session_id)
        )
        task = Task(method.__name__, apply_result)
        self.in_queue[session_id].append(task)
        log.info("session {}: task {} added to queue".format(session_id, task.name))
        return True

    def on_task_complete(self, result, task_name, session_id):
        """
        :param result: str
        :param task_name: str
        :param session_id: int
        """
        log.debug("session {}: task {} completed with return value '{}'".format(session_id, task_name, result))
        session_tasks = self.in_queue[session_id]
        for task in session_tasks[:]:
            if task.name == task_name:
                session_tasks.remove(task)
                break
        else:
            log.warning("session {}: task {} not found".format(session_id, task_name))

        if not self.in_queue[session_id]:
            log.debug("session {}: all tasks done".format(session_id))
            self.in_queue.pop(session_id, None)

    def del_tasks_for_session(self, session_id):
        """
        :param session_id: int
        """
        log.info("session {} tasks: {}".format(session_id, [task.name for task in self.in_queue[session_id]]))
        for task in self.in_queue[session_id]:
            if task.apply_result and not task.apply_result.ready():
                try:
                    task.apply_result.wait(timeout=1)
                    log.warning("session {}: aborting task {}".format(session_id, task))
                except:
                    log.exception("session {}: task {} abortion was failured".format(session_id, task))
        self.in_queue.pop(session_id, None)

    def del_tasks(self, sessions_ids):
        """
        :param sessions_ids: list
        """
        log.info("Deleting tasks for {} sessions: {}".format(
            len(self.in_queue.keys()), self.in_queue.keys()
        ))
        for session_id in sessions_ids:
            self.del_tasks_for_session(session_id)

    def wait_for_complete(self, session_id):
        """
        :param session_id: int
        """
        start = time.time()
        timeout = getattr(config, "COLLECT_ARTIFACTS_WAIT_TIMEOUT", 60)

        while session_id in self.in_queue.keys():
            log.debug("session {}: wait for {} tasks to complete".format(
                session_id, len(self.in_queue[session_id])
            ))
            if time.time() - start > timeout:
                log.warning("session {}: timeout {} while waiting for tasks".format(session_id, timeout))
                self.del_tasks_for_session(session_id)
                break
            time.sleep(1)

        log.info("session {}: all tasks completed".format(session_id))

    def stop(self):
        self.del_tasks(self.in_queue.keys())
        self.terminate()
        self.join()
        log.info("ArtifactCollector was stopped")

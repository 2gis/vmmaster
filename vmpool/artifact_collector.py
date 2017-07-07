# coding: utf-8

import os
import json
import time
import logging
import websocket

from threading import Thread
from collections import defaultdict
from flask import current_app
from multiprocessing.pool import ThreadPool

from core import utils
from core.config import config


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
    for code, headers, body in get_artifact_from_endpoint(session, original_path):
        pass

    if code == 200:
        path = os.sep.join(
            [config.SCREENSHOTS_DIR, str(session.id), "%s.log" % filename]
        )
        try:
            body = json.loads(body)
            utils.write_file(path, body.get("output", "no data"))
            new_path = path
            log.debug("File %s was saved to %s " % (filename, new_path))
        except:
            log.exception("Selenium log file %s doesn't created for session %s"
                          % (filename, session.id))
    return new_path


def get_artifact_from_endpoint(session, path):
    """
    :param session: Session
    :param path: str
    :return: status, headers, body
    """
    host = "ws://%s:%s/runScript" % (session.endpoint_ip,
                                     config.VMMASTER_AGENT_PORT)
    script = '{"command": "sudo -S sh", "script": "cat %s"}' % path
    log.debug("Run script for session {}, cmd={}".format(session, script))
    for status, headers, body in run_script(script, host):
        yield None, None, None

    yield status, headers, body


def save_selenium_log(session_id, filename, original_path):
    """
    :param session_id: int
    :param filename: str
    :param original_path: str
    """
    session = get_session_from_db(session_id)

    if not session:
        log.error("Session %s not found and selenium log doesn't saved" % session_id)
        return

    log_path = save_artifact(session, filename, original_path)
    if log_path:
        session.selenium_log = log_path
        session.save()
        log.info("Selenium log saved to %s for session %s" % (log_path, session_id))
    else:
        log.warning("Selenium log doesn't saved for session %s" % session_id)


def on_completed_task(session_id):
    """
    :param session_id: int
    """
    log.debug("Completing task for session %s" % session_id)
    session = get_session_from_db(session_id)

    if not session:
        log.error("Task doesn't sucessfully finished for session %s "
                  "and endpoint doesn't deleted" % session_id)
        return

    endpoint = current_app.pool.get_by_name(session.endpoint_name)
    if endpoint:
        endpoint.delete()
    log.debug("Task finished for session %s" % session_id)


def get_session_from_db(session_id):
    """
    :param session_id: int
    :return: Session
    """
    session = None
    try:
        session = current_app.database.get_session(session_id)
    except:
        log.exception("Session %s not found" % session_id)

    return session


class ArtifactCollector(ThreadPool):
    def __init__(self, vmpool):
        if hasattr(config, "ARTIFACT_COLLECTOR_PROCESSES"):
            super(ArtifactCollector, self).__init__(
                processes=config.ARTIFACT_COLLECTOR_PROCESSES
            )
        else:
            super(ArtifactCollector, self).__init__()
        self.in_queue = defaultdict(list)
        self.vmpool = vmpool
        log.info("ArtifactCollector started")

    def __reduce__(self):
        super(ArtifactCollector, self).__reduce__()

    def get_queue(self):
        return self.in_queue.keys()

    def add_task(self, session_id, artifact_name, artifact_path):
        """
        :param session_id: int
        :param artifact_name: str
        :param artifact_path: str
        :return: True or False
        """
        if artifact_name == "selenium_server":
            self.run_task(
                session_id,
                self.save_selenium_log,
                args=(session_id, artifact_name, artifact_path)
            )
            return True
        else:
            log.warning("Task not found for session %s" % session_id)
            return False

    def run_task(self, session_id, method, args):
        apply_result = self.apply_async(method, args=args)
        log.debug("Apply Result %s" % apply_result)
        self.in_queue[session_id].append(apply_result)
        log.info("Task for getting artifacts added to queue for session %s" % session_id)

    def add_tasks(self, session_id, artifacts):
        """
        :param session_id: int
        :param artifacts: dict
        :return: list of True or False
        """
        result = True
        for artifact_name, artifact_path in artifacts.items():
            completed = self.add_task(session_id, artifact_name, artifact_path)
            if not completed:
                result = False

        return result

    def del_task(self, session_id):
        """
        :param session_id: int
        """
        tasks = self.in_queue[session_id]
        for task in tasks:
            if task and not task.ready():
                task.successful()
                log.info("Getting artifacts for session %s aborted" % session_id)
        try:
            del self.in_queue[session_id]
        except KeyError:
            log.exception("Tasks already deleted from queue for session %s" % session_id)
        log.info("Getting artifacts abort has been failed for "
                 "session %s because it's already done" % session_id)

    def del_tasks(self, sessions_ids):
        """
        :param sessions_ids: list
        """
        for session_id in sessions_ids:
            self.del_task(session_id)

    def save_selenium_log(self, session_id, artifact_name, artifact_path):
        """
        :param session_id: int
        :param artifact_name: str
        :param artifact_path: str
        """
        with self.vmpool.app.app_context():
            try:
                save_selenium_log(session_id, artifact_name, artifact_path)
            except:
                log.exception("Error saving selenium log for session {} ({}: {})"
                              .format(session_id, artifact_name, artifact_path))
            finally:
                self.in_queue.pop(session_id)
                on_completed_task(session_id)

    def wait_for_complete(self):
        start = time.time()
        timeout = getattr(config, "COLLECT_ARTIFACTS_WAIT_TIMEOUT", 60)

        while self.in_queue:
            log.info("Wait for tasks to complete: {}".format(
                [(session, len(tasks)) for session, tasks in self.in_queue.items()])
            )
            time.sleep(1)
            if time.time() - start > timeout:
                log.warning("Timeout {} while waiting for tasks".format(timeout))
                return

        log.info("All tasks completed.")

    def stop(self):
        self.terminate()
        self.del_tasks(self.in_queue.keys())
        self.close()
        log.info("ArtifactCollector stopped")

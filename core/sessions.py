# coding: utf-8

import time
import logging

from threading import Thread  # TODO: stop using threading.Thread, replace with twisted.reactor.callInThread
from flask import current_app

from core.config import config
from core.exceptions import SessionException

log = logging.getLogger(__name__)


def update_log_step(log_step, message=None, control_line=None):
    if message:
        log_step.body = message
    if control_line:
        log_step.control_line = control_line
    log_step.save()


class SimpleResponse:
    def __init__(self, status_code=None, headers=None, content=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content


class SessionWorker(Thread):
    def __init__(self, sessions):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.sessions = sessions

    def run(self):
        # TODO: remove app_context usage
        with self.sessions.app.app_context():
            while self.running:
                for session in self.sessions.running():
                    if not session.is_active \
                            and session.inactivity > config.SESSION_TIMEOUT:
                        session.timeout()
                time.sleep(1)

    def stop(self):
        self.running = False
        self.join()
        log.info("SessionWorker stopped")


class Sessions(object):
    def __init__(self, app):
        self.app = app
        self.worker = SessionWorker(self)

    def start_workers(self):
        self.worker.start()

    def stop_workers(self):
        self.worker.stop()

    def active(self, provider_id=None):
        return self.app.database.get_active_sessions(provider_id=provider_id)

    def running(self):
        return [s for s in self.active() if s.status == "running"]

    def waiting(self):
        return [s for s in self.active() if s.status == "waiting"]

    def kill_all(self):
        for session in self.active():
            session.failed()

    @staticmethod
    def get_session(session_id, maybe_closed=False):
        session = current_app.database.get_session(session_id)
        session_maybe_closed = True if maybe_closed else not getattr(session, "closed", True)

        if session and session_maybe_closed:
            log.debug("Recovering {} from db".format(session))
            session.restore()
        elif getattr(session, "closed", False):
            raise SessionException("Session {}({}) already closed earlier".format(session_id, session.reason))
        else:
            raise SessionException("There is no active session {} (Unknown session)".format(session_id))

        return session

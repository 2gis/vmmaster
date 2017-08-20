# coding: utf-8

import time
import logging

from threading import Thread
from datetime import datetime
from flask import current_app

from core import constants
from core.db import models
from core.config import config
from core.exceptions import SessionException
from core.utils import network_utils

log = logging.getLogger(__name__)


class RequestHelper(object):
    method = None
    url = None
    headers = None
    data = None

    def __init__(self, method, url="/", headers=None, data=""):
        _headers = {}
        if headers:
            for key, value in headers.items():
                if value:
                    _headers[key] = value
        _headers["Content-Length"] = str(len(data))
        self.headers = _headers
        self.method = method
        self.url = url
        self.data = data

    def __repr__(self):
        return "<RequestHelper method:%s url:%s headers:%s body:%s>" % (
            self.method, self.url, self.headers, self.data)


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


class Session(models.BaseSession):
    endpoint = None
    current_log_step = None
    take_screencast = None
    is_active = True

    def __init__(self, name=None, dc=None):
        super(Session, self).__init__(name, dc)
        if dc and dc.get('takeScreencast', None):
            self.take_screencast = True
        self.save()

    def __str__(self):
        return "Session id={} status={}".format(self.id, self.status)

    @property
    def inactivity(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def duration(self):
        return (datetime.now() - self.created).total_seconds()

    @property
    def is_done(self):
        return self.status in ('failed', 'succeed')

    @property
    def info(self):
        stat = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "platform": self.platform,
            "duration": self.duration,
            "inactivity": self.inactivity,
        }

        if self.endpoint_name:
            stat["endpoint"] = {
                "ip": self.endpoint_ip,
                "name": self.endpoint_name
            }
        return stat

    def start_timer(self):
        self.modified = datetime.now()
        self.save()
        self.is_active = False

    def stop_timer(self):
        self.is_active = True

    def save_artifacts(self):
        artifacts = {
            "selenium_server": "/var/log/selenium_server.log"
        }
        if not self.endpoint_ip:
            return False
        return self.endpoint.save_artifacts(self, artifacts)

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if getattr(self, "endpoint", None):
            self.endpoint.stop_recorder()
            if not self.take_screencast and "succeed" in self.status:
                self.endpoint.vnc_helper.delete_source_video()

        if hasattr(self, "ws"):
            self.ws.close()

        if getattr(self, "endpoint", None) and not self.save_artifacts():
            log.info("Deleting endpoint %s (%s) for session %s" %
                     (self.endpoint_name, self.endpoint_ip, self.id))
            self.endpoint.delete()

        log.info("Session %s closed. %s" % (self.id, self.reason))

    def succeed(self):
        self.status = "succeed"
        self.close()

    def failed(self, tb=None, reason=None):
        if self.closed:
            log.warn("Session %s already closed with reason %s. "
                     "In this method call was tb='%s' and reason='%s'"
                     % (self.id, self.reason, tb, reason))
            return

        self.status = "failed"
        self.error = tb
        self.close(reason)

    def set_vm(self, endpoint):
        self.endpoint_ip = endpoint.ip
        self.endpoint_name = endpoint.name

    def run(self, endpoint):
        self.modified = datetime.now()
        self.endpoint = endpoint
        self.endpoint.start_recorder(self.id)
        self.set_vm(endpoint)
        self.status = "running"
        self.save()
        log.info("Session %s starting on %s (%s)." %
                 (self.id, self.endpoint_name, self.endpoint_ip))

    def timeout(self):
        self.timeouted = True
        self.failed(reason="Session timeout. No activity since %s" %
                    str(self.modified))

    def add_sub_step(self, control_line, body=None):
        if self.current_log_step:
            return self.current_log_step.add_sub_step(control_line, body)

    def add_session_step(self, control_line, body=None, created=None):
        step = super(Session, self).add_session_step(
            control_line=control_line, body=body, created=created
        )
        self.current_log_step = step
        return step

    def make_request(self, port, request, timeout=constants.REQUEST_TIMEOUT):
        return network_utils.make_request(self.endpoint_ip, port, request, timeout)


class SessionWorker(Thread):
    def __init__(self, sessions):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.sessions = sessions

    def run(self):
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
        self.worker.start()

    def start_worker(self):
        self.worker.start()

    def stop_worker(self):
        self.worker.stop()

    def active(self):
        return self.app.database.get_active_sessions()

    def running(self):
        return [s for s in self.active() if s.status == "running"]

    def waiting(self):
        return [s for s in self.active() if s.status == "waiting"]

    def kill_all(self):
        for session in self.active():
            session.close()

    @staticmethod
    def get_session(session_id):
        session = current_app.database.get_session(session_id)

        if session and not session.closed:
            session.current_log_step = current_app.database.get_last_session_step(session_id)
            session.endpoint = current_app.pool.get_by_name(session.endpoint_name)
        elif getattr(session, "closed", False):
            raise SessionException("There is no active session {} ({})".format(session_id, session.reason))
        else:
            raise SessionException("There is no active session {} (Unknown session)".format(session_id))

        return session

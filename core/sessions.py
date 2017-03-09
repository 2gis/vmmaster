# coding: utf-8

import time
import requests
import logging

from Queue import Queue
from threading import Thread
from datetime import datetime
from flask import current_app

from core.db import models
from core.config import config
from core.exceptions import SessionException
from core.video import VNCVideoHelper

log = logging.getLogger(__name__)


def getresponse(req, q):
    try:
        q.put(req())
    except Exception as e:
        q.put(e)


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
        _headers["Content-Length"] = len(data)
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


class VMMasterSession(models.Session):
    current_log_step = None
    vnc_helper = None
    take_screencast = None
    is_active = True

    def __str__(self):
        return "Session id=%s status=%s" % (self.id, self.status)

    def __init__(self, name=None, dc=None):
        super(VMMasterSession, self).__init__(name, dc)
        if dc and dc.get('takeScreencast', None):
            self.take_screencast = True

    @property
    def inactivity(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def duration(self):
        return (datetime.now() - self.created).total_seconds()

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

        if self.endpoint:
            stat["endpoint"] = {
                "ip": self.endpoint.ip,
                "name": self.endpoint.name
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
        return self.endpoint.save_artifacts(self, artifacts)

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if self.vnc_helper:
            self.vnc_helper.stop_recording()
            self.vnc_helper.stop_proxy()

        if hasattr(self, "ws"):
            self.ws.close()

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

    def run(self):
        self.modified = datetime.now()
        self.status = "running"
        self.vnc_helper = VNCVideoHelper(self.endpoint.ip,
                                         filename_prefix=self.id)

        if self.take_screencast:
            self.vnc_helper.start_recording()

        log.info("Session %s starting on %s (%s)." %
                 (self.id, self.endpoint.name, self.endpoint.ip))
        self.save()

    def timeout(self):
        self.timeouted = True
        self.failed(reason="Session timeout. No activity since %s" %
                    str(self.modified))

    def add_sub_step(self, control_line, body=None):
        if self.current_log_step:
            return self.current_log_step.add_sub_step(control_line, body)

    def add_session_step(self, control_line, body=None, created=None):
        step = super(VMMasterSession, self).add_session_step(
            control_line=control_line, body=body, created=created
        )
        self.current_log_step = step
        self.save()
        self.refresh()
        log.warning("LOG STEP: %s" % self.current_log_step.id)

        return step

    def make_request(self, port, request):
        """ Make http request to some port in session
            and return the response. """

        if request.headers.get("Host"):
            del request.headers['Host']

        q = Queue()
        url = "http://%s:%s%s" % (self.endpoint.ip, port, request.url)

        def req():
            return requests.request(method=request.method,
                                    url=url,
                                    headers=request.headers,
                                    data=request.data)

        t = Thread(target=getresponse, args=(req, q))
        t.daemon = True
        t.start()

        while t.isAlive():
            yield None, None, None

        response = q.get()
        if isinstance(response, Exception):
            raise response

        yield response.status_code, response.headers, response.content


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
        if not session:
            raise SessionException("There is no active session %s" % session_id)
        return session

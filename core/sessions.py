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


class Session(models.Session):
    current_log_step = None
    vnc_helper = None
    take_screencast = None
    is_active = True

    def __init__(self, name=None, dc=None):
        super(Session, self).__init__(name, dc)
        if dc and dc.get('takeScreencast', None):
            self.take_screencast = True

        current_app.sessions.put(self)

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

        if self.endpoint_name:
            stat["endpoint"] = {
                "ip": self.endpoint_ip,
                "name": self.endpoint_name
            }
        return stat

    def set_user(self, username):
        self.user = current_app.database.get_user(username=username)

    def start_timer(self):
        self.modified = datetime.now()
        self.save()
        self.is_active = False

    def stop_timer(self):
        self.is_active = True

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if self.vnc_helper:
            self.vnc_helper.stop_recording()
            self.vnc_helper.stop_proxy()

        current_app.sessions.remove(self)

        if hasattr(self, "ws"):
            self.ws.close()

        if hasattr(self, "endpoint") and self.endpoint:
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
        self.set_vm(endpoint)
        self.status = "running"
        self.vnc_helper = VNCVideoHelper(self.endpoint_ip,
                                         filename_prefix=self.id)

        if self.take_screencast:
            self.vnc_helper.start_recording()

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

    def make_request(self, port, request):
        """ Make http request to some port in session
            and return the response. """

        if request.headers.get("Host"):
            del request.headers['Host']

        q = Queue()
        url = "http://%s:%s%s" % (self.endpoint_ip, port, request.url)

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
    active_sessions = {}

    def __init__(self, app):
        self.app = app
        self.worker = SessionWorker(self)
        self.worker.start()

    def put(self, session):
        if str(session.id) not in self.active_sessions.keys():
            self.active_sessions[str(session.id)] = session
        else:
            raise SessionException("Duplicate session id: %s" % session.id)

    def remove(self, session):
        try:
            del self.active_sessions[str(session.id)]
        except KeyError:
            pass

    def active(self):
        return self.active_sessions.values()

    def running(self):
        return [s for s in self.active() if s.status == "running"]

    def waiting(self):
        return [s for s in self.active() if s.status == "waiting"]

    def kill_all(self):
        for session in self.active_sessions.values():
            session.close()

    def get_session(self, session_id):
        try:
            session = self.active_sessions[str(session_id)]
        except KeyError:
            session = current_app.database.get_session(session_id)
            if session:
                reason = session.reason
            else:
                reason = "Unknown session"

            message = "There is no active session %s" % session_id
            if reason:
                message = "%s (%s)" % (message, reason)

            raise SessionException(message)

        return session

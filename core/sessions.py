# coding: utf-8

import time
from datetime import datetime
from Queue import Queue
from threading import Thread

import requests
import logging
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

from core.db.models import Session as SessionModel
from core.config import config
from core.logger import log
from core.exceptions import SessionException
from vmpool.endpoint import delete_vm

from flask import current_app


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
            self.method, self.url, self.headers, self.body)


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


class Session(SessionModel):
    def __init__(self, name=None, dc=None):
        super(Session, self).__init__(name, dc)
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

    def get_milestone_step(self):
        """
        Find last session log step marked as milestone for sub_step
        :return: SessionLogStep object
        """
        return current_app.database.get_last_step(self)

    def set_user(self, username):
        self.user = current_app.database.get_user(username=username)

    def restart_timer(self):
        self.modified = datetime.now()
        self.save()

    def delete(self, message=""):
        current_app.sessions.remove(self)
        if hasattr(self, "endpoint"):
            log.info("Deleting VM for session: %s" % self.id)
            self.endpoint.delete()
        else:
            delete_vm(self.endpoint_name)
        log.info("Session %s deleted. %s" % (self.id, message))

    def succeed(self):
        self.status = "succeed"
        self.closed = True
        self.save()
        self.delete()

    def failed(self, tb="Session closed by user"):
        self.status = "failed"
        self.closed = True
        self.error = tb
        self.save()
        self.delete(tb)

    def set_vm(self, endpoint):
        self.endpoint_ip = endpoint.ip
        self.endpoint_name = endpoint.name

    def run(self, endpoint):
        self.restart_timer()
        self.set_vm(endpoint)
        self.status = "running"

        log.info("Session %s starting on %s." % (self.id, self.endpoint_name))

    def timeout(self):
        self.timeouted = True
        self.failed("Session timeout")

    def add_sub_step(self, control_line, body=None):
        current_milestone_step = self.get_milestone_step()
        if current_milestone_step:
            return current_milestone_step.add_sub_step(control_line, body)

    def make_request(self, port, request):
        """ Make http request to some port in session
            and return the response. """

        if request.headers.get("Host"):
            del request.headers['Host']

        self.restart_timer()
        q = Queue()
        url = "http://%s:%s%s" % (self.endpoint_ip, port, request.url)

        req = lambda: requests.request(method=request.method,
                                       url=url,
                                       headers=request.headers,
                                       data=request.data)
        t = Thread(target=getresponse, args=(req, q))
        t.daemon = True
        t.start()

        response = None
        while t.isAlive():
            yield None, None, None

        response = q.get()
        if isinstance(response, Exception):
            raise response

        yield response.status_code, response.headers, response.content


class SessionWorker(Thread):
    def __init__(self, app):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.app = app

    def run(self):
        with self.app.app_context():
            while self.running:
                for session in self.app.sessions.active():
                    if session.inactivity > config.SESSION_TIMEOUT:
                        session.timeout()
                time.sleep(1)

    def stop(self):
        self.running = False
        self.join()
        log.info("SessionWorker stopped")


class Sessions(object):
    active_sessions = dict()

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

    def kill_all(self):
        for session in self.active_sessions.values():
            session.delete()

    def get_session(self, session_id):
        try:
            session = self.active_sessions[str(session_id)]
        except KeyError:
            raise SessionException(
                "There is no active session %s" % session_id
            )

        if session.closed:
            if session.timeouted:
                raise SessionException(
                    "Session %s timeouted" % session_id
                )
            else:
                raise SessionException(
                    "Session %s closed" % session_id
                )

        return session

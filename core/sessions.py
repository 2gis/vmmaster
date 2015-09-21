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

    @property
    def inactivity(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def duration(self):
        return (datetime.now() - self.created).total_seconds()

    def is_timeouted(self):
        self.refresh()
        return self.timeouted

    def is_closed(self):
        self.refresh()
        return self.closed

    @property
    def info(self):
        self.refresh()
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
        self.refresh()
        if self.endpoint_name:
            log.info("Deleting VM for session: %s" % self.id)

            from vmpool.api.endpoint import delete_vm
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
        self.endpoint_ip = endpoint.get('ip', None)
        self.endpoint_name = endpoint.get('name', None)

    def run(self, endpoint):
        self.restart_timer()
        self.set_vm(endpoint)
        self.status = "running"

        log.info("Session %s starting on %s." % (self.id, self.endpoint_name))

    def timeout(self):
        self.refresh()
        self.timeouted = True
        self.save()
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
        while not response:
            if self.timeouted:
                response = SimpleResponse(
                    status_code=500,
                    headers={},
                    content='{"status": 1, "value": "Session timeouted"}'
                )
            elif self.closed:
                response = SimpleResponse(
                    status_code=500,
                    headers={},
                    content='{"status": 1, "value": "Session closed"}'
                )
            else:
                if not t.isAlive():
                    response = q.get()
                    del q
                    del t
                    if isinstance(response, Exception):
                        raise response
                    response = SimpleResponse(
                        status_code=response.status_code,
                        headers=response.headers,
                        content=response.content
                    )
                    t = None
                elif t is not None:
                    t.join(0.1)

        return response.status_code, response.headers, response.content


class SessionWorker(Thread):
    def __init__(self, app):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.app = app

    def active_sessions(self):
        return self.app.database.get_sessions()

    def run(self):
        with self.app.app_context():
            while self.running:
                for session in self.active_sessions():
                    if session.inactivity > config.SESSION_TIMEOUT:
                        session.timeout()
                time.sleep(1)

    def stop(self):
        self.running = False
        self.join()
        log.info("SessionWorker stopped")


class Sessions(object):
    @staticmethod
    def get_session(session_id):
        session = current_app.database.get_session(session_id)

        if not session or session.is_closed():
            raise SessionException("There is no active session %s" %
                                   session_id)

        session.refresh()
        return session

import time
import base64
import sys
from threading import Thread
from traceback import format_exc

from flask import request, Request, Response

from . import commands

from .config import config
from .logger import log
from .utils.utils import write_file
from .db import database
from .exceptions import SessionException, ConnectionError
from .sessions import RequestHelper


class BucketThread(Thread):
    def __init__(self, bucket, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.bucket = bucket

    def run(self):
        try:
            super(BucketThread, self).run()
        except Exception:
            self.bucket.put(sys.exc_info())


class Request(Request):
    def __init__(self):
        super(Request, self).__init__(request.environ)
        self.clientproto = self.headers.environ['SERVER_PROTOCOL']
        headers = dict()
        for key, value in self.headers.items():
            if value:
                headers[key] = value
        self.headers = headers
        self.body = self.data


class SessionProxy(object):
    def __init__(self):
        self.request = Request()
        self.response = None
        self._session_id = None

    @property
    def session_id(self):
        # return commands.get_session_id(self.request.path)
        if not self._session_id:
            self._session_id = commands.get_session_id(self.request.path)
        return self._session_id

    @session_id.setter
    def session_id(self, value):
        self._session_id = value


class PlatformHandler(object):
    _headers = None
    _body = None

    _reply_code = None
    _reply_headers = None
    _reply_body = None

    _log_step = None
    _session_id = None

    def __init__(self, platforms, sessions):
        self.platforms = platforms
        self.sessions = sessions

    def __call__(self, path):
        proxy = SessionProxy()
        response = self.request_received(proxy)
        self.log_write(proxy.session_id, response.status, str(response.data))
        return response

    def request_received(self, proxy):
        req = proxy.request
        if proxy.session_id:
            proxy._log_step = self.log_write(proxy.session_id, "%s %s %s" % (req.method, req.path, req.clientproto), str(req.body))

        try:
            return self.process_request(proxy)
        except:
            return self.handle_exception(proxy, format_exc())

    def handle_exception(self, request, tb):
        log.error(tb)
        resp = self.form_response(code=500, headers={"Content-Length": len(tb)}, body=tb)
        try:
            session = self.sessions.get_session(request.session_id)
        except SessionException:
            pass
        else:
            session.failed(tb)
        return resp

    @staticmethod
    def log_write(session_id, control_line, body):
        return database.createLogStep(
            session_id=session_id,
            control_line=control_line,
            body=body,
            time=time.time()
        )

    def take_screenshot(self, proxy):
        session = self.sessions.get_session(proxy.session_id)
        screenshot = commands.take_screenshot(session, 9000)

        if screenshot:
            path = config.SCREENSHOTS_DIR + "/" + str(proxy.session_id) + "/" + str(proxy._log_step.id) + ".png"
            write_file(path, base64.b64decode(screenshot))
            return path

    def process_request(self, proxy):
        req = proxy.request
        method = getattr(self, "do_" + req.method)
        method(proxy)
        if req.input_stream._wrapped.closed:
            raise ConnectionError("Client has disconnected")

        return proxy.response

    @staticmethod
    def form_response(code, headers, body):
        """ Send reply to client. """
        if not code:
            code = 500
            body = "Something ugly happened. No real reply formed."
            headers = {
                'Content-Length': len(body)
            }
        return Response(response=body, status=code, headers=headers)

    def swap_session(self, req, desired_session):
        req.body = commands.set_body_session_id(req.body, desired_session)
        req.path = commands.set_path_session_id(req.path, desired_session)
        if req.body:
            req.headers['Content-Length'] = len(req.body)

    def transparent(self, proxy):
        req = proxy.request
        session = self.sessions.get_session(proxy.session_id)
        self.swap_session(req, session.selenium_session)
        code, headers, response_body = session.make_request(
            config.SELENIUM_PORT,
            RequestHelper(req.method, req.path, req.headers, req.body)
        )

        self.swap_session(req, proxy.session_id)
        return self.form_response(code, headers, response_body)

    def do_POST(self, proxy):
        """POST request."""
        req = proxy.request
        if req.path.split("/")[-1] == "session":
            session = commands.create_session(req, self.sessions)
            proxy.session_id = session.id
            proxy._log_step = self.log_write(
                proxy.session_id, "%s %s %s" % (req.method, req.path, req.clientproto), str(req.body))
            status, headers, body = commands.start_session(req, session, self.platforms)
            proxy.response = self.form_response(status, headers, body)
        else:
            proxy.response = self.transparent(proxy)

        words = ["url", "click", "execute", "keys", "value"]
        parts = req.path.split("/")
        path = None
        if set(words) & set(parts) or parts[-1] == "session":
            path = self.take_screenshot(proxy)

        if proxy._log_step and path:
            proxy._log_step.screenshot = path
            database.update(proxy._log_step)

    def do_GET(self, proxy):
        """GET request."""
        proxy.response = self.transparent(proxy)

    def do_DELETE(self, proxy):
        """DELETE request."""
        req = proxy.request
        if req.path.split("/")[-2] == "session":
            proxy.response = self.transparent(proxy)
            self.sessions.get_session(proxy.session_id).succeed()
        else:
            proxy.response = self.transparent(proxy)

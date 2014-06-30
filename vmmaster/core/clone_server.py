import httplib
import copy
import time
import base64
import sys
from threading import Thread
from Queue import Queue

from twisted.internet.threads import deferToThread
from twisted.web.proxy import Proxy
from twisted.web.http import Request, HTTPFactory

from . import commands

from .config import config
from .logger import log
from .utils.utils import write_file
from .db import database
from .exceptions import TimeoutException
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


class RequestHandler(Request):
    _headers = None
    _body = None

    _reply_code = None
    _reply_headers = None
    _reply_body = None

    _log_step = None
    _session_id = None

    def __init__(self, *args):
        Request.__init__(self, *args)
        self.clone_factory = self.channel.factory.clone_factory
        self.sessions = self.channel.factory.sessions

    @property
    def headers(self):
        """get headers dictionary"""
        if self._headers:
            return self._headers

        self._headers = self.getAllHeaders()
        return self._headers

    @property
    def body(self):
        """get request body."""
        if self._body:
            return self._body

        data = copy.copy(self.content)

        if self.getHeader('Content-Length') is None:
            self._body = None
        else:
            content_length = int(self.getHeader('Content-Length'))
            self._body = data.read(content_length)

        del data
        return self._body

    @property
    def session_id(self):
        if self._session_id:
            return self._session_id

        self._session_id = commands.get_session_id(self.path)
        return self._session_id

    def requestReceived(self, command, path, version):
        Request.requestReceived(self, command, path, version)
        if self.session_id:
            self._log_step = database.createLogStep(
                session_id=self.session_id,
                control_line="%s %s %s" % (command, path, version),
                body=str(self.body),
                time=time.time())

        # request to thread
        d = deferToThread(self.processRequest)
        d.addErrback(lambda failure: RequestHandler.handle_exception(self, failure))
        d.addBoth(RequestHandler.finish)

    def finish(self):
        self.perform_reply()
        Request.finish(self)

    def handle_exception(self, failure):
        tb = failure.getTraceback()
        log.error(tb)
        self.form_reply(code=500, headers={}, body=tb)
        try:
            self.sessions.get_session(self.session_id).failed(tb)
        except KeyError:
            pass
        return self

    def take_screenshot(self):
        clone = self.sessions.get_session(self.session_id).clone
        screenshot = commands.take_screenshot(clone.get_ip(), 9000)

        path = config.SCREENSHOTS_DIR + "/" + str(self.session_id) + "/" + str(self._log_step.id) + ".png"
        write_file(path, base64.b64decode(screenshot))
        return path

    def processRequest(self):
        method = getattr(self, "do_" + self.method)
        error_bucket = Queue()
        th = BucketThread(
            target=method, name=repr(method), bucket=error_bucket
        )
        th.daemon = True
        th.start()

        while th.isAlive():
            th.join(0.1)

            if not error_bucket.empty():
                error = error_bucket.get(block=False)
                raise error[0], error[1], error[2]

            try:
                session = self.sessions.get_session(self.session_id)
            except KeyError:
                pass
            else:
                if session.timeouted:
                    raise TimeoutException("Session timeout")
        return self

    def form_reply(self, code, headers, body):
        """ Send reply to client. """
        # reply code
        self._reply_code = code

        # reply headers
        self._reply_headers = {}
        for keyword, value in headers.items():
            self._reply_headers[keyword] = value

        # reply body
        self._reply_body = body

    def perform_reply(self):
        """ Perform reply to client. """
        if not self._reply_code:
            self._reply_code = 500
            self._reply_body = "Something ugly happened. No real reply formed."
            self._reply_headers = {
                'content-length': len(self._reply_body)
            }

        if self.session_id:
            database.createLogStep(
                session_id=self.session_id,
                control_line="%s %s" % (self.clientproto, self._reply_code),
                body=str(self._reply_body),
                time=time.time())

        self.setResponseCode(self._reply_code)

        for keyword, value in self._reply_headers.items():
            self.setHeader(keyword, value)

        self.write(self._reply_body)

    def swap_session(self, desired_session):
        self.body = commands.set_body_session_id(self.body, desired_session)
        self.path = commands.set_path_session_id(self.path, desired_session)
        if self.body:
            self.headers['content-length'] = len(self.body)

    def transparent(self, method):
        session = self.sessions.get_session(self.session_id)
        self.swap_session(session.selenium_session)
        code, headers, response_body = session.make_request(
            config.SELENIUM_PORT,
            RequestHelper(method, self.path, self.headers, self.body)
        )
        self.swap_session(self.session_id)
        self.form_reply(code, headers, response_body)

    def do_POST(self):
        """POST request."""
        if self.path.split("/")[-1] == "session":
            commands.create_session(self)
        else:
            self.transparent("POST")

        words = ["url", "click", "execute", "keys", "value"]
        parts = self.path.split("/")
        path = None
        if set(words) & set(parts) or parts[-1] == "session":
            path = self.take_screenshot()

        if self._log_step and path:
            self._log_step.screenshot = path
            database.update(self._log_step)

        return self

    def do_GET(self):
        """GET request."""
        self.transparent("GET")
        return self

    def do_DELETE(self):
        """DELETE request."""
        if self.path.split("/")[-2] == "session":
            commands.delete_session(self)
        else:
            self.transparent("DELETE")
        return self


class RequestProxy(Proxy):
    requestFactory = RequestHandler


class ProxyFactory(HTTPFactory):
    log = lambda *args: None
    protocol = RequestProxy

    def __init__(self, clone_factory, sessions):
        HTTPFactory.__init__(self)
        self.clone_factory = clone_factory
        self.sessions = sessions

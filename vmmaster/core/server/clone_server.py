import httplib
import copy

from twisted.internet import protocol
from twisted.internet.threads import deferToThread
from twisted.web.proxy import Proxy
from twisted.web.http import Request, HTTPFactory

from vmmaster.core.server import commands
from vmmaster.core.config import config
from vmmaster.core.logger import log


class RequestHandler(Request):
    _headers = None
    _body = None

    _reply_code = None
    _reply_headers = None
    _reply_body = None

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

    def finish(self):
        self.perform_reply()
        Request.finish(self)

    def handle_exception(self, failure):
        tb = failure.getTraceback()
        log.error(tb)
        self.form_reply(code=500, headers={}, body=tb)
        return self

    def process(self):
        method = getattr(self, "do_" + self.method)
        d = deferToThread(method)
        d.addErrback(lambda failure: RequestHandler.handle_exception(self, failure))
        d.addBoth(RequestHandler.finish)

    def make_request(self, method, url, headers, body):
        """ Make request to selenium-server-standalone
            and return the response. """
        clone = self.sessions.get_clone(commands.get_session(self))
        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=clone.get_ip(), port=config.SELENIUM_PORT))
        conn.request(method=method, url=url, headers=headers, body=body)

        clone.get_timer().restart()

        response = conn.getresponse()

        if response.getheader('Content-Length') is None:
            response_body = None
        else:
            content_length = int(response.getheader('Content-Length'))
            response_body = response.read(content_length)

        conn.close()

        return response.status, dict(x for x in response.getheaders()), response_body

    def form_reply(self, code, headers, body):
        """ Send reply to client. """
        # reply code
        self._reply_code = code
        # self.setResponseCode(code)

        # reply headers
        self._reply_headers = {}
        for keyword, value in headers.items():
            self._reply_headers[keyword] = value
            # self.setHeader(keyword, value)

        # reply body
        self._reply_body = body
        # self.write(body)

    def perform_reply(self):
        """ Perform reply to client. """
        self.setResponseCode(self._reply_code)

        for keyword, value in self._reply_headers.items():
            self.setHeader(keyword, value)

        self.write(self._reply_body)

    def transparent(self, method):
        code, headers, response_body = self.make_request(method, self.path, self.headers, self.body)
        self.form_reply(code, headers, response_body)

    def do_POST(self):
        """POST request."""
        if self.path.split("/")[-1] == "session":
            commands.create_session(self)
        else:
            self.transparent("POST")
        return self

    def do_GET(self):
        """GET request."""
        self.transparent("GET")
        return self

    def do_DELETE(self):
        """DELETE request."""
        if self.path.split("/")[-3] == "session":
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
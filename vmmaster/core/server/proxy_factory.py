import httplib
import copy

from twisted.internet import protocol
from twisted.web.proxy import Proxy
from twisted.web.http import Request

from vmmaster.core.server import commands
from vmmaster.core.config import config
from vmmaster.core.logger import log


class RequestHandler(Request):
    _headers = None
    _body = None

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

    def process(self):
        method = getattr(self, "do_" + self.method)
        try:
            method()
        except:
            import traceback
            tb = traceback.format_exc()
            self.send_reply(code=500, headers={}, body=tb)
            log.error(tb)

        self.finish()

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

        return response.status, response.getheaders(), response_body

    def send_reply(self, code, headers, body):
        """ Send reply to client. """
        # reply code
        self.setResponseCode(code)

        # reply headers
        for keyword, value in headers:
            self.setHeader(keyword, value)

        # reply body
        self.write(body)

    def transparent(self, method):
        code, headers, response_body = self.make_request(method, self.path, self.headers, self.body)
        self.send_reply(code, headers, response_body)

    def do_POST(self):
        """POST request."""
        if self.path.split("/")[-1] == "session":
            commands.create_session(self)
        else:
            self.transparent("POST")
        return

    def do_GET(self):
        """GET request."""
        self.transparent("GET")
        return

    def do_DELETE(self):
        """DELETE request."""
        if self.path.split("/")[-3] == "session":
            commands.delete_session(self)
        else:
            self.transparent("DELETE")
        return


class Proxy(Proxy):
    requestFactory = RequestHandler


class ProxyFactory(protocol.Factory):
    log = lambda *args: None
    protocol = Proxy

    def __init__(self, clone_factory, sessions):
        self.clone_factory = clone_factory
        self.sessions = sessions
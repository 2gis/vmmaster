from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import httplib
import copy

from vmmaster.core.clone_factory import CloneFactory
from vmmaster.core.network.sessions import Sessions
from vmmaster.core.network.network import Network
from vmmaster.core.config import config
from vmmaster.core.logger import log

from vmmaster.core.server import commands


class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, clone_factory, sessions, *args):
        self.clone_factory = clone_factory
        self.sessions = sessions
        BaseHTTPRequestHandler.__init__(self, *args)

    @property
    def body(self):
        """get request body."""
        data = copy.copy(self.rfile)

        if self.headers.getheader('Content-Length') is None:
            body = None
        else:
            content_length = int(self.headers.getheader('Content-Length'))
            body = data.read(content_length)

        return body

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
        self.send_response(code)

        # reply headers
        for keyword, value in headers:
            self.send_header(keyword, value)
        self.end_headers()

        # reply body
        self.wfile.write(body)
        return

    def transparent(self, method):
        code, headers, response_body = self.make_request(method, self.path, self.headers.dict, self.body)
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
        if self.path.split("/")[-2] == "session":
            commands.delete_session(self)
        else:
            self.transparent("DELETE")
        return

    def log_request(self, code=None, size=None):
        host, port = self.client_address
        log.info("{client} - {request} {code}".format(
            client=host,
            request=self.raw_requestline.rstrip(),
            code=code)
        )

    # def log_message(self, format, *args):
    #     return


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class VMMasterServer(object):
    def __init__(self, server_address):
        # creating network
        self.network = Network()
        self.clone_factory = CloneFactory()
        self.sessions = Sessions()

        # server props
        self.server_address = server_address
        self.handler = self.handleRequestsUsing(self.clone_factory, self.sessions)

    def __del__(self):
        self.clone_factory.delete()
        self.network.delete()

    def handleRequestsUsing(self, clone_factory, sessions):
        return lambda *args: RequestHandler(clone_factory, sessions, *args)

    def run(self):
        server = ThreadedHTTPServer(self.server_address, self.handler)
        server.serve_forever()
from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import httplib
import copy
import json
import StringIO
import threading

from config import Config
from vmmaster.core.clone_factory import CloneFactory
from vmmaster.utils import network_utils
from vmmaster.core.network.sessions import Sessions

clone_factory = CloneFactory()
sessions = Sessions()


class RequestHandler(BaseHTTPRequestHandler):
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

    def set_substituted_body(self, body):
        self.substituted_body = body

    def make_request(self, method, url, headers, body):
        """ Make request to selenium-server-standalone
            and return the response. """
        ip = sessions.get_ip(self.get_session())
        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=Config.selenium_port))
        conn.request(method=method, url=url, headers=headers, body=body)

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
        session = self.get_session()
        print session
        code, headers, response_body = self.make_request(method, self.path, self.headers.dict, self.body)
        self.send_reply(code, headers, response_body)

    def do_GET(self):
        """GET request."""
        self.transparent("GET")
        return

    def replace_platform_with_any(self):
        body = json.loads(self.body)
        desired_capabilities = body["desiredCapabilities"]

        desired_capabilities["platform"] = u"ANY"
        body["desiredCapabilities"] = desired_capabilities

        new_body = StringIO.StringIO(json.dumps(body))
        self.rfile = new_body
        self.headers.dict["content-length"] = len(self.body)
        return

    def get_platform(self):
        body = json.loads(self.body)
        desired_capabilities = body["desiredCapabilities"]
        platform = desired_capabilities["platform"]
        return platform

    def get_session(self):
        path = self.path
        parts = path.split("/")
        pos = parts.index("session")
        session = parts[pos + 1]
        return session

    def create_session(self):
        platform = self.get_platform()
        self.replace_platform_with_any()
        ip = clone_factory.create_clone(platform)
        network_utils.ping(ip, Config.selenium_port, 3600)

        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=Config.selenium_port))
        conn.request(method="POST", url=self.path, headers=self.headers.dict, body=self.body)

        response = conn.getresponse()

        if response.getheader('Content-Length') is None:
            response_body = None
        else:
            content_length = int(response.getheader('Content-Length'))
            response_body = response.read(content_length)
        conn.close()

        print response_body
        sessionId = json.loads(response_body)["sessionId"]
        sessions.add_session(sessionId, ip)

        self.send_reply(response.status, response.getheaders(), response_body)
        return

    def do_POST(self):
        """POST request."""
        if self.path.split("/")[-1] == "session":
            self.create_session()
        else:
            self.transparent("POST")
        return

    def do_DELETE(self):
        """DELETE request."""
        self.transparent("DELETE")
        return

        # def log_request(self, code=None, size=None):
        #     print('Request')
        #
        # def log_message(self, format, *args):
        #     print('Message')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class VMMasterServer(object):
    def __init__(self, server_address):
        self.server_address = server_address

    def run(self):
        server = ThreadedHTTPServer(self.server_address, RequestHandler)
        server.serve_forever()
from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn, ForkingMixIn
import httplib
import copy
import json
import StringIO

from vmmaster.core.clone_factory import CloneFactory
from vmmaster.utils import network_utils
from vmmaster.core.network.sessions import Sessions
from vmmaster.core.network.network import Network
from vmmaster.core.config import config
from vmmaster.core.logger import log


class StatusException():
    pass


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

    def set_substituted_body(self, body):
        self.substituted_body = body

    def make_request(self, method, url, headers, body):
        """ Make request to selenium-server-standalone
            and return the response. """
        clone = self.sessions.get_clone(self.get_session())
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

    def selenium_status(self, ip, port):
        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))

        parts = self.path.split("/")
        parts[-1] = "status"
        status = "/".join(parts)

        # try to get status for 3 times
        for check in range(3):
            conn.request(method="GET", url=status)
            response = conn.getresponse()
            if response.status == httplib.OK:
                log.debug("SUCCESS get selenium-server-standalone status for {}:{}".format(ip, port))
                log.debug(response.read())
                conn.close()
                return True
            else:
                log.debug("FAIL    get selenium-server-standalone status for {}:{}".format(ip, port))

        conn.close()
        return False

    def session_response(self, ip, port):
        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))

        # try to get status for 3 times
        for check in range(3):
            conn.request(method="POST", url=self.path, headers=self.headers.dict, body=self.body)
            response = conn.getresponse()
            if response.status == httplib.OK:
                conn.close()
                return response

            # need to read response
            body = response.read()
            log.info("{status} : {body}".format(status=response.status, body=body))

        conn.close()
        return response

    def create_session(self):
        platform = self.get_platform()
        self.replace_platform_with_any()
        clone = self.clone_factory.create_clone(platform)

        # ping ip:port
        network_utils.ping(clone.get_ip(), config.SELENIUM_PORT, config.PING_TIMEOUT)

        # check status
        if not self.selenium_status(clone.get_ip(), config.SELENIUM_PORT):
            self.clone_factory.utilize_clone(clone)
            ### @todo: every exception got to be sent back to client
            raise StatusException("failed to get status of selenium-server-standalone")

        response = self.session_response(clone.get_ip(), config.SELENIUM_PORT)

        if response.getheader('Content-Length') is None:
            response_body = None
        else:
            content_length = int(response.getheader('Content-Length'))
            response_body = response.read(content_length)

        if response.status != httplib.OK:
            self.clone_factory.utilize_clone(clone)
        else:
            sessionId = json.loads(response_body)["sessionId"]
            self.sessions.add_session(sessionId, clone)

        self.send_reply(response.status, response.getheaders(), response_body)
        return

    def delete_session(self):
        self.transparent("DELETE")
        clone = self.sessions.get_clone(self.get_session())
        self.clone_factory.utilize_clone(clone)
        return

    def do_POST(self):
        """POST request."""
        if self.path.split("/")[-1] == "session":
            self.create_session()
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
            self.delete_session()
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
import unittest
import threading
import BaseHTTPServer
import copy

import vmmaster.core.server.commands
from vmmaster.core.config import setup_config, config
from vmmaster.core.clone_factory import CloneFactory


def stub():
    pass


class Mock(object):
    pass


class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
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

    def do_POST(self):
        reply = self.headers.getheader("reply")
        code = int(reply)
        self.send_reply(code, self.headers.dict.iteritems(), body=self.body)

    def log_error(self, format, *args):
        pass


class Server(object):
    def __init__(self, host, port):
        self._server_address = (host, port)
        self._server = BaseHTTPServer.HTTPServer(self._server_address, Handler)
        self._server.timeout = 1
        self._running = None
        self._thread = threading.Thread(target=self._run_server)

    def __del__(self):
        self.stop()

    def _run_server(self):
        while self._running:
            self._server.handle_request()

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread.join()


class TestCommands(unittest.TestCase):
    session_request_headers = {
        'content-length': '144',
        'accept-encoding': 'identity',
        'Connection': 'close',
        'accept': 'application/json',
        'user-agent': 'Python-urllib/2.7',
        'host': '127.0.0.1:9000',
        'content-type': 'application/json;charset=UTF-8',
    }
    session_request_body = '{"sessionId": null, "desiredCapabilities": {"platform": "ubuntu-13.04-x65", "browserName": "firefox", "version": "", "javascriptEnabled": true}}'

    session_request = Mock()
    session_request.path = "/wd/hub/session"
    session_request.headers = Mock()
    session_request.headers.dict = session_request_headers
    session_request.body = session_request_body

    @classmethod
    def setUpClass(cls):
        setup_config('config.py')

        cls.host = 'localhost'
        cls.port = 4567
        cls.server = Server(cls.host, cls.port)
        cls.server.start()

        cls.create_session_reply_200 = copy.deepcopy(cls.session_request)
        cls.create_session_reply_200.headers.dict.update({"reply": "200"})

        cls.create_session_reply_500 = copy.deepcopy(cls.session_request)
        cls.create_session_reply_500.headers.dict.update({"reply": "500"})

        CloneFactory.create_clone = stub
        CloneFactory.utilize_clone = stub

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    #def test_create_session(self):
    #    vmmaster.core.server.commands.create_session(self.create_session_reply_200, self.host, self.port)

    def test_session_response_success(self):
        request = self.create_session_reply_200
        response = vmmaster.core.server.commands.session_response(request, self.host, self.port)
        self.assertEqual(response.status, 200)

        request_headers = dict((key.lower(), value) for key, value in request.headers.dict.iteritems())
        response_headers = dict((key.lower(), value) for key, value in response.getheaders())
        for key, value in response_headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(response.read(), request.body)

    def test_session_response_fail(self):
        request = self.create_session_reply_500
        response = vmmaster.core.server.commands.session_response(request, self.host, self.port)
        self.assertEqual(response.status, 500)

        request_headers = dict((key.lower(), value) for key, value in request.headers.dict.iteritems())
        response_headers = dict((key.lower(), value) for key, value in response.getheaders())
        for key, value in response_headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(response.read(), request.body)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCommands)
    unittest.TextTestRunner(verbosity=2).run(suite)
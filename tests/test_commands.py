# coding: utf-8

import unittest
import threading
import BaseHTTPServer
import copy
import json

from mock import Mock

# Mocking
from vmmaster.core import db
db.database = Mock()
from vmmaster.core.sessions import Session

from vmmaster.core import commands
from vmmaster.core.config import setup_config
from vmmaster.core.sessions import Sessions


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

    def log_message(self, format, *args):
        pass

    def log_request(self, code='-', size='-'):
        pass


class WebDriverRemoteMock(object):
    def __init__(self, host, port):
        self._server_address = (host, port)
        self._server = BaseHTTPServer.HTTPServer(self._server_address, Handler)
        self._server.timeout = 1
        self._server.allow_reuse_address = True
        self._thread = threading.Thread(target=self._server.serve_forever)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.server_close()
        self._server.shutdown()
        while self._thread.isAlive():
            self._thread.join()


class TestCommands(unittest.TestCase):
    webdriver_server = None

    @classmethod
    def setUpClass(cls):
        setup_config("data/config.py")
        body = {
            "sessionId": None,
            "desiredCapabilities": {
                "platform": "some_platform",
                "browserName": "firefox",
                "version": "",
                "javascriptEnabled": True
            }
        }
        session_request_body = json.dumps(body)
        session_request_headers = {
            'content-length': '%s' % len(session_request_body),
            'accept-encoding': 'identity',
            'Connection': 'close',
            'accept': 'application/json',
            'user-agent': 'Python-urllib/2.7',
            'host': '127.0.0.1:9000',
            'content-type': 'application/json;charset=UTF-8',
        }

        session_request = Mock()
        session_request.method = "POST"
        session_request.path = "/wd/hub/session"
        session_request.headers = dict()
        session_request.headers.update(session_request_headers)
        session_request.body = session_request_body

        cls.host = 'localhost'
        cls.port = 4567
        cls.webdriver_server = WebDriverRemoteMock(cls.host, cls.port)
        cls.webdriver_server.start()

        cls.create_session_reply_200 = copy.deepcopy(session_request)
        cls.create_session_reply_200.headers.update({"reply": "200"})

        cls.create_session_reply_500 = copy.deepcopy(session_request)
        cls.create_session_reply_500.headers.update({"reply": "500"})
        Session.virtual_machine = Mock(ip=cls.host)
        cls.sessions = Sessions()

    @classmethod
    def tearDownClass(cls):
        cls.webdriver_server.stop()

    def setUp(self):
        self.session = self.sessions.start_session("test")

    def tearDown(self):
        self.session.delete()

    def test_session_response_success(self):
        request = self.create_session_reply_200
        status, headers, body = commands.start_selenium_session(request, self.session, self.port)
        self.assertEqual(status, 200)

        request_headers = dict((key.lower(), value) for key, value in request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.body)

    def test_session_response_fail(self):
        request = self.create_session_reply_500
        status, headers, body = commands.start_selenium_session(request, self.session, self.port)
        self.assertEqual(status, 500)

        request_headers = dict((key.lower(), value) for key, value in request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.body)

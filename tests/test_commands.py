# coding: utf-8

import unittest
import threading
import BaseHTTPServer
import copy
import json
import sys

from mock import Mock

# Mocking
from vmmaster.core import db
db.database = Mock()
from vmmaster.core.sessions import Session

from vmmaster.core import commands
from vmmaster.core.config import setup_config, config
from vmmaster.core.sessions import Sessions
from vmmaster.core.exceptions import CreationException


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
        for keyword, value in headers.iteritems():
            self.send_header(keyword, value)
        self.end_headers()

        # reply body
        self.wfile.write(body)

    def do_POST(self):
        reply = self.headers.getheader("reply")
        code = int(reply)
        self.send_reply(code, self.headers.dict, body=self.body)

    def do_GET(self):
        raise NotImplemented

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


class CommonCommandsTestCase(unittest.TestCase):
    webdriver_server = None
    host = None
    port = None

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
        cls.request = Mock()
        cls.request.method = "POST"
        cls.request.path = "/wd/hub/session"
        cls.request.headers = dict()
        cls.request.headers.update(session_request_headers)
        cls.request.body = session_request_body

        cls.host = 'localhost'
        cls.port = 4567
        cls.webdriver_server = WebDriverRemoteMock(cls.host, cls.port)
        cls.webdriver_server.start()

        Session.virtual_machine = Mock(ip=cls.host)
        cls.sessions = Sessions()

    @classmethod
    def tearDownClass(cls):
        cls.webdriver_server.stop()

    def setUp(self):
        self.session = self.sessions.start_session("test", "test_origin_1")

    def tearDown(self):
        self.session.delete()


class TestStartSeleniumSessionCommands(CommonCommandsTestCase):
    def test_session_response_success(self):
        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})
        status, headers, body = commands.start_selenium_session(request, self.session, self.port)
        self.assertEqual(status, 200)

        request_headers = dict((key.lower(), value) for key, value in request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.body)

    def test_session_response_fail(self):
        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "500"})
        status, headers, body = commands.start_selenium_session(request, self.session, self.port)
        self.assertEqual(status, 500)

        request_headers = dict((key.lower(), value) for key, value in request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.body)
        print body


class TestCheckVmOnline(CommonCommandsTestCase):
    def setUp(self):
        super(TestCheckVmOnline, self).setUp()
        config.PING_TIMEOUT = 0
        config.SELENIUM_PORT = self.port

        self._handler_get = Handler.do_GET
        self.response_body = "some_body"
        self.response_headers = {
            'header': 'value',
            'content-length': len(self.response_body)
        }

    def tearDown(self):
        super(TestCheckVmOnline, self).tearDown()
        Handler.do_GET = self._handler_get

    def test_check_vm_online_ok(self):
        def do_GET(handler):
            handler.send_reply(200, self.response_headers, body=self.response_body)
        Handler.do_GET = do_GET
        result = commands.ping_vm(self.session)
        self.assertTrue(result)

    def test_check_vm_online_ping_failed(self):
        config.SELENIUM_PORT = self.port + 1
        result = commands.ping_vm(self.session)
        self.assertFalse(result)

    def test_check_vm_online_status_failed(self):
        def do_GET(handler):
            handler.send_reply(500, self.response_headers, body=self.response_body)
        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)
        result = commands.selenium_status(request, self.session, self.port)
        self.assertFalse(result)

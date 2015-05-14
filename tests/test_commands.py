# coding: utf-8

import unittest
import threading
import BaseHTTPServer
import copy
import json
import socket
import requests

from mock import Mock, patch

# Mocking db
from vmmaster.core import db
with patch.object(db, 'database', Mock(name='Database')):
    from vmmaster.webdriver import commands
    from vmmaster.core.config import setup_config, config
    from vmmaster.core.sessions import Sessions, Session
    from vmmaster.core.virtual_machine import VirtualMachine
    from vmmaster.core.exceptions import CreationException


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


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


class ServerMock(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._server = BaseHTTPServer.HTTPServer((host, port), Handler)
        self._server.timeout = 1
        self._server.allow_reuse_address = True
        self._thread = threading.Thread(target=self._server.serve_forever)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


class CommonCommandsTestCase(unittest.TestCase):
    webdriver_server = None
    vmmaster_agent = None
    host = 'localhost'

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

        cls.webdriver_server = ServerMock(cls.host, get_free_port())
        cls.webdriver_server.start()
        cls.vmmaster_agent = ServerMock(cls.host, get_free_port())
        cls.vmmaster_agent.start()

        with patch.object(Session, "virtual_machine"):
            Session.virtual_machine = Mock(ip=cls.host)
            cls.sessions = Sessions()

    @classmethod
    def tearDownClass(cls):
        cls.webdriver_server.stop()
        cls.vmmaster_agent.stop()

    def setUp(self):
        vm = VirtualMachine()
        vm.ip = self.host
        self.session = self.sessions.start_session("test", "test_origin_1", vm)

    def tearDown(self):
        self.session.delete()


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"}))
))
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="ping_vm")
)
class TestStartSessionCommands(CommonCommandsTestCase):
    def setUp(self):
        super(TestStartSessionCommands, self).setUp()
        self.session.desired_capabilities = Mock()
        self.session.desired_capabilities.runScript = False

    def test_start_session_when_selenium_status_failed(self):
        with patch.object(Session, "make_request",
                          side_effect=Mock(
                              __name__="make_request",
                              return_value=(200, {}, json.dumps({'status': 1}))
                          )):
                request = copy.copy(self.request)
                self.assertRaises(CreationException, commands.start_session, request, self.session)

    def test_start_session_when_session_was_timeouted(self):
        with patch.object(requests, "request",
                          side_effect=Mock(
                              __name__="request",
                              return_value=(200, {}, json.dumps({'status': 0}))
                          )):
                self.session.timeouted = True
                request = copy.copy(self.request)
                self.assertRaises(CreationException, commands.start_session, request, self.session)

    def test_start_session_when_session_was_closed(self):
        with patch.object(requests, "request",
                          side_effect=Mock(
                              __name__="request",
                              return_value=(200, {}, json.dumps({'status': 0}))
                          )):
                self.session.closed = True
                request = copy.copy(self.request)
                self.assertRaises(CreationException, commands.start_session, request, self.session)


class TestStartSeleniumSessionCommands(CommonCommandsTestCase):
    def test_session_response_success(self):
        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})
        status, headers, body = commands.start_selenium_session(
            request, self.session, self.webdriver_server.port)
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
        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)

    def test_start_selenium_session_when_session_closed(self):
        self.session.closed = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)

    def test_start_selenium_session_when_session_timeouted(self):
        self.session.timeouted = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)


class TestCheckVmOnline(CommonCommandsTestCase):
    def setUp(self):
        super(TestCheckVmOnline, self).setUp()
        config.PING_TIMEOUT = 0
        config.SELENIUM_PORT = self.webdriver_server.port
        config.VMMASTER_AGENT_PORT = self.vmmaster_agent.port

        self._handler_get = Handler.do_GET
        self.response_body = "{}"
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

    def test_check_vm_online_ping_failed_timeout(self):
        config.SELENIUM_PORT = get_free_port()
        self.assertRaises(CreationException, commands.ping_vm, self.session)

    def test_check_vm_online_ping_failed_when_session_closed(self):
        config.PING_TIMEOUT = 2
        self.session.closed = True
        self.assertRaises(CreationException, commands.ping_vm, self.session)

    def test_check_vm_online_status_failed(self):
        def do_GET(handler):
            handler.send_reply(500, self.response_headers, body=self.response_body)
        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)
        self.assertRaises(CreationException, commands.selenium_status,
                          request, self.session, self.webdriver_server.port)

    def test_selenium_status_failed_when_session_closed(self):
        self.session.closed = True

        def do_GET(handler):
            handler.send_reply(200, self.response_headers, body=self.response_body)

        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)

        self.assertRaises(CreationException, commands.selenium_status,
                          request, self.session, self.webdriver_server.port)


class TestGetDesiredCapabilities(unittest.TestCase):
    def setUp(self):
        self.body = {
            "sessionId": None,
            "desiredCapabilities": {
                "platform": "some_platform",
            }
        }
        self.session_request_headers = {
            'content-length': '%s',
            'accept-encoding': 'identity',
            'Connection': 'close',
            'accept': 'application/json',
            'user-agent': 'Python-urllib/2.7',
            'host': '127.0.0.1:9000',
            'content-type': 'application/json;charset=UTF-8',
        }

        self.request = Mock()
        self.request.method = "POST"
        self.request.path = "/wd/hub/session"
        self.request.headers = dict()

    def test_platform(self):
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc.platform, unicode)
        self.assertEqual(self.body["desiredCapabilities"]["platform"], dc.platform)

    def test_name(self):
        self.body['desiredCapabilities'].update({
            "name": "some_name"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc.name, unicode)
        self.assertEqual(self.body["desiredCapabilities"]["name"], dc.name)

    def test_no_name(self):
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertEqual(dc.name, None)

    def test_take_screenshot_bool(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": True
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertTrue(dc.takeScreenshot)

    def test_take_screenshot_some_string(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": "asdf"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertTrue(dc.takeScreenshot)

    def test_take_screenshot_empty_string(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": ""
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertFalse(dc.takeScreenshot)


class TestRunScript(CommonCommandsTestCase):
    def setUp(self):
        super(TestRunScript, self).setUp()
        config.VMMASTER_AGENT_PORT = self.vmmaster_agent.port

        self._handler_post = Handler.do_POST
        self.response_body = "some_body"
        self.response_headers = {
            'header': 'value',
            'content-length': str(len(self.response_body))
        }

    def tearDown(self):
        super(TestRunScript, self).tearDown()
        Handler.do_POST = self._handler_post

    def test_run_script(self):
        def do_POST(handler):
            handler.send_reply(200, self.response_headers, body=self.response_body)
        Handler.do_POST = do_POST
        response = commands.run_script(self.request, self.session)
        self.assertEqual(200, response[0])
        self.assertDictContainsSubset(self.response_headers, response[1])
        self.assertEqual(self.response_body, response[2])


class TestLabelCommands(CommonCommandsTestCase):
    def test_label(self):
        request = copy.deepcopy(self.request)
        label = "step-label"
        request.body = json.dumps({"label": label})
        status, headers, body = commands.vmmaster_label(request, self.session)
        self.assertEqual(status, 200)
        json_body = json.loads(body)
        self.assertEqual(json_body["value"], label)


# coding: utf-8

import copy
import json

from mock import Mock, PropertyMock, patch
from tests.helpers import Handler, BaseTestCase, ServerMock, get_free_port, DatabaseMock

from core.exceptions import CreationException, ConnectionError, \
    SessionException, TimeoutException
from core.config import setup_config, config
from flask import Flask


class CommonCommandsTestCase(BaseTestCase):
    webdriver_server = None
    vmmaster_agent = None
    vnc_server = None
    host = 'localhost'

    @classmethod
    def setUpClass(cls):
        setup_config("data/config_openstack.py")
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
        cls.request.data = session_request_body

        cls.webdriver_server = ServerMock(cls.host, get_free_port())
        cls.webdriver_server.start()
        cls.vmmaster_agent = ServerMock(cls.host, get_free_port())
        cls.vmmaster_agent.start()
        cls.vnc_server = ServerMock(cls.host, get_free_port())
        cls.vnc_server.start()

        cls.app = Flask(__name__)
        cls.app.database = None
        cls.app.sessions = None
        cls.app.pool = Mock()

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()

        with patch(
            'flask.current_app.database', DatabaseMock()
        ), patch(
            'flask.current_app.sessions', Mock()
        ):
            from core.sessions import Session
            self.session = Session('origin_1')
            self.session.name = "session1"

            vm = PropertyMock()
            vm.name = 'vm1'
            vm.ip = self.host
            vm.vnc_port = self.vnc_server.port
            vm.selenium_port = self.webdriver_server.port
            vm.agent_port = self.vmmaster_agent.port
            self.session.endpoint = vm

            self.session.run()

            from vmmaster.webdriver import commands
            self.commands = commands

    def tearDown(self):
        with patch(
            'flask.current_app.sessions', Mock()
        ), patch(
            'flask.current_app.database', Mock()
        ):
            self.session.close()
        self.ctx.pop()

    @classmethod
    def tearDownClass(cls):
        cls.webdriver_server.stop()
        cls.vmmaster_agent.stop()
        cls.vnc_server.stop()
        del cls.app


def ping_vm_mock(arg, ports=None):
    yield None


def selenium_status_mock(arg1, arg2, arg3):
    yield None


@patch(
    'vmmaster.webdriver.commands.start_selenium_session', new=Mock(
        __name__="start_selenium_session",
        side_effect=selenium_status_mock
    )
)
@patch(
    'vmmaster.webdriver.commands.ping_vm',
    new=Mock(__name__="ping_vm", side_effect=ping_vm_mock)
)
@patch(
    'vmmaster.webdriver.helpers.is_request_closed',
    Mock(return_value=False)
)
@patch('flask.current_app.database', Mock())
class TestStartSessionCommands(CommonCommandsTestCase):
    def setUp(self):
        super(TestStartSessionCommands, self).setUp()
        self.session.dc = Mock(__name__="dc")

    def test_start_session_when_selenium_status_failed(self):
        request = copy.copy(self.request)

        def make_request_mock(arg1, arg2):
            yield 200, {}, json.dumps({'status': 1})

        with patch(
            'core.sessions.Session.make_request', Mock(
                __name__="make_request",
                side_effect=make_request_mock
            )
        ):
            self.assertRaises(
                CreationException, self.commands.start_session,
                request, self.session
            )

    @patch(
        'vmmaster.webdriver.helpers.is_session_timeouted',
        Mock(return_value=True)
    )
    @patch(
        'requests.request', Mock(side_effect=Mock(
            __name__="request",
            return_value=(200, {}, json.dumps({'status': 0}))))
    )
    def test_start_session_when_session_was_timeouted(self):
        request = copy.copy(self.request)
        self.assertRaises(TimeoutException, self.commands.start_session,
                          request, self.session)

    @patch(
        'vmmaster.webdriver.helpers.is_session_closed',
        Mock(return_value=True)
    )
    @patch(
        'requests.request', Mock(side_effect=Mock(
            __name__="request",
            return_value=(200, {}, json.dumps({'status': 0}))))
    )
    def test_start_session_when_session_was_closed(self):
        request = copy.copy(self.request)
        self.assertRaises(SessionException, self.commands.start_session,
                          request, self.session)


@patch('flask.current_app.database', Mock())
class TestStartSeleniumSessionCommands(CommonCommandsTestCase):
    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_value=False)
    )
    def test_session_response_success(self):
        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        status, headers, body = self.commands.start_selenium_session(
            request, self.session
        )

        self.assertEqual(status, 200)

        request_headers = dict((key.lower(), value) for key, value in
                               request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.data)

    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_value=False)
    )
    def test_session_response_fail(self):
        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "500"})

        def start_selenium_session(req):
            for result in self.commands.start_selenium_session(
                req, self.session
            ):
                pass

        self.assertRaises(CreationException, start_selenium_session, request)

    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_value=True)
    )
    def test_start_selenium_session_when_connection_closed(self):
        self.session.closed = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(
            ConnectionError, self.commands.start_selenium_session,
            request, self.session
        )

    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_value=False)
    )
    @patch(
        'vmmaster.webdriver.helpers.is_session_closed',
        Mock(return_value=True)
    )
    def test_start_selenium_session_when_session_closed(self):
        self.session.closed = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(
            SessionException, self.commands.start_selenium_session,
            request, self.session
        )

    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_value=False)
    )
    @patch(
        'vmmaster.webdriver.helpers.is_session_timeouted',
        Mock(return_value=True)
    )
    def test_start_selenium_session_when_session_timeouted(self):
        self.session.closed = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(
            TimeoutException, self.commands.start_selenium_session,
            request, self.session
        )


@patch(
    'vmmaster.webdriver.helpers.is_request_closed',
    Mock(return_value=False)
)
@patch('flask.current_app.database', Mock())
class TestCheckVmOnline(CommonCommandsTestCase):
    def setUp(self):
        super(TestCheckVmOnline, self).setUp()
        config.PING_TIMEOUT = 0
        config.SELENIUM_PORT = self.webdriver_server.port
        config.VMMASTER_AGENT_PORT = self.vmmaster_agent.port
        config.VNC_PORT = self.vnc_server.port

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
            handler.send_reply(200, self.response_headers,
                               body=self.response_body)
        Handler.do_GET = do_GET
        result = self.commands.ping_vm(self.session, ports=[
            self.webdriver_server.port, self.vmmaster_agent.port, self.vnc_server.port
        ])
        self.assertTrue(result)

    def test_check_vm_online_ping_failed_timeout(self):
        config.SELENIUM_PORT = get_free_port()

        self.assertRaises(
            CreationException, self.commands.ping_vm, self.session
        )

    def test_check_vm_online_ping_failed_when_session_closed(self):
        config.PING_TIMEOUT = 2
        self.session.closed = True

        self.assertRaises(
            CreationException, self.commands.ping_vm, self.session
        )

    def test_check_vm_online_status_failed(self):
        def do_GET(handler):
            handler.send_reply(500, self.response_headers,
                               body=self.response_body)
        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)

        def selenium_status(req):
            for result in self.commands.selenium_status(
                req, self.session
            ):
                pass

        self.assertRaises(CreationException, selenium_status, request)

    def test_selenium_status_failed_when_session_closed(self):
        self.session.closed = True

        def do_GET(handler):
            handler.send_reply(200, self.response_headers,
                               body=self.response_body)

        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)

        def selenium_status(req):
            for result in self.commands.selenium_status(
                req, self.session
            ):
                pass

        self.assertRaises(CreationException, selenium_status, request)


class TestGetDesiredCapabilities(BaseTestCase):
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

        from vmmaster.webdriver import commands
        self.commands = commands

    def test_platform(self):
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)
        dc = self.commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc["platform"], unicode)
        self.assertEqual(self.body["desiredCapabilities"]["platform"],
                         dc["platform"])

    def test_name(self):
        self.body['desiredCapabilities'].update({
            "name": "some_name"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)

        dc = self.commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc["name"], unicode)
        self.assertEqual(self.body["desiredCapabilities"]["name"], dc["name"])

    def test_no_name(self):
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)
        dc = self.commands.get_desired_capabilities(self.request)
        self.assertEqual(dc.get("name", None), None)

    def test_take_screenshot_bool(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": True
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)
        dc = self.commands.get_desired_capabilities(self.request)
        self.assertTrue(dc["takeScreenshot"])

    def test_take_screenshot_some_string(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": "asdf"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)
        dc = self.commands.get_desired_capabilities(self.request)
        self.assertTrue(dc["takeScreenshot"])

    def test_take_screenshot_empty_string(self):
        self.body['desiredCapabilities'].update({
            "takeScreenshot": ""
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.data = json.dumps(self.body)
        dc = self.commands.get_desired_capabilities(self.request)
        self.assertFalse(dc["takeScreenshot"])


class TestRunScript(CommonCommandsTestCase):
    def setUp(self):
        super(TestRunScript, self).setUp()
        config.VMMASTER_AGENT_PORT = self.vmmaster_agent.port
        self.response_body = "some_body"

    def tearDown(self):
        super(TestRunScript, self).tearDown()

    @patch('flask.current_app.database', Mock())
    def test_run_script(self):
        def run_script_through_websocket_mock(*args, **kwargs):
            return 200, {}, 'some_body'

        with patch('vmmaster.webdriver.commands.run_script_through_websocket',
                   run_script_through_websocket_mock):
            response = self.commands.run_script(self.request, self.session)

        self.assertEqual(200, response[0])
        self.assertEqual(self.response_body, response[2])


class TestLabelCommands(CommonCommandsTestCase):
    def test_label(self):
        request = copy.deepcopy(self.request)
        label = "step-label"
        label_id = 1
        request.data = json.dumps({"label": label})
        with patch('core.sessions.Session.current_log_step',
                   PropertyMock(return_value=Mock(id=label_id))):
            status, headers, body = self.commands.vmmaster_label(
                request, self.session
            )

        self.assertEqual(status, 200)
        json_body = json.loads(body)
        self.assertEqual(json_body["value"], label)
        self.assertEqual(json_body["labelId"], label_id)

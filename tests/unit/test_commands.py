# coding: utf-8

import copy
import json

from mock import Mock, patch
from helpers import Handler, BaseTestCase
from helpers import ServerMock, get_free_port

from vmmaster.core.exceptions import CreationException
from vmmaster.core.config import setup_config, config


class CommonCommandsTestCase(BaseTestCase):
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

    def setUp(self):
        with patch('vmmaster.core.db.database', Mock()):
            from vmmaster.core.sessions import Session
            self.session = Session()
            self.session.id = 1
            self.session.name = "session1"
            self.session.platform = "test_origin_1"

            from vmpool import VirtualMachine
            vm = VirtualMachine("vm1", "test_origin_1")
            vm.id = 1
            vm.ip = self.host

            with patch('vmmaster.core.db.database.get_vm', Mock(
                    return_value=vm)):
                self.session.run(vm)

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()), \
                patch('vmmaster.core.utils.utils.del_endpoint', Mock()):
            self.session.delete()

    @classmethod
    def tearDownClass(cls):
        cls.webdriver_server.stop()
        cls.vmmaster_agent.stop()


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(__name__="ping_vm"))
@patch('vmmaster.core.db.database', Mock())
class TestStartSessionCommands(CommonCommandsTestCase):
    def setUp(self):
        super(TestStartSessionCommands, self).setUp()
        self.session.dc = Mock(__name__="dc")

    def test_start_session_when_selenium_status_failed(self):
        with patch('vmmaster.core.sessions.Session.make_request',
                   side_effect=Mock(
                       __name__="make_request",
                       return_value=(200, {}, json.dumps({'status': 1})))):
                request = copy.copy(self.request)

                from vmmaster.webdriver import commands
                self.assertRaises(CreationException, commands.start_session,
                                  request, self.session)

    def test_start_session_when_session_was_timeouted(self):
        with patch('requests.request', side_effect=Mock(
                __name__="request",
                return_value=(200, {}, json.dumps({'status': 0})))):
                self.session.timeouted = True
                request = copy.copy(self.request)

                from vmmaster.webdriver import commands
                self.assertRaises(CreationException, commands.start_session,
                                  request, self.session)

    def test_start_session_when_session_was_closed(self):
        with patch('requests.request', side_effect=Mock(
                __name__="request",
                return_value=(200, {}, json.dumps({'status': 0})))):
                self.session.closed = True
                request = copy.copy(self.request)

                from vmmaster.webdriver import commands
                self.assertRaises(CreationException, commands.start_session,
                                  request, self.session)


@patch('vmmaster.core.db.database', Mock())
class TestStartSeleniumSessionCommands(CommonCommandsTestCase):
    def test_session_response_success(self):
        from vmmaster.webdriver import commands

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})
        status, headers, body = commands.start_selenium_session(
            request, self.session, self.webdriver_server.port)
        self.assertEqual(status, 200)

        request_headers = dict((key.lower(), value) for key, value in
                               request.headers.iteritems())
        for key, value in headers.iteritems():
            if key == 'server' or key == 'date':
                continue
            self.assertDictContainsSubset({key: value}, request_headers)
        self.assertEqual(body, request.body)

    def test_session_response_fail(self):
        from vmmaster.webdriver import commands

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "500"})
        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)

    def test_start_selenium_session_when_session_closed(self):
        from vmmaster.webdriver import commands

        self.session.closed = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)

    def test_start_selenium_session_when_session_timeouted(self):
        from vmmaster.webdriver import commands

        self.session.timeouted = True

        request = copy.deepcopy(self.request)
        request.headers.update({"reply": "200"})

        self.assertRaises(CreationException, commands.start_selenium_session,
                          request, self.session, self.webdriver_server.port)


@patch('vmmaster.core.db.database', Mock())
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
        from vmmaster.webdriver import commands

        def do_GET(handler):
            handler.send_reply(200, self.response_headers,
                               body=self.response_body)
        Handler.do_GET = do_GET
        result = commands.ping_vm(self.session)
        self.assertTrue(result)

    def test_check_vm_online_ping_failed_timeout(self):
        from vmmaster.webdriver import commands

        config.SELENIUM_PORT = get_free_port()
        self.assertRaises(CreationException, commands.ping_vm, self.session)

    def test_check_vm_online_ping_failed_when_session_closed(self):
        from vmmaster.webdriver import commands

        config.PING_TIMEOUT = 2
        self.session.closed = True
        self.assertRaises(CreationException, commands.ping_vm, self.session)

    def test_check_vm_online_status_failed(self):
        from vmmaster.webdriver import commands

        def do_GET(handler):
            handler.send_reply(500, self.response_headers,
                               body=self.response_body)
        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)
        self.assertRaises(CreationException, commands.selenium_status,
                          request, self.session, self.webdriver_server.port)

    def test_selenium_status_failed_when_session_closed(self):
        from vmmaster.webdriver import commands
        self.session.closed = True

        def do_GET(handler):
            handler.send_reply(200, self.response_headers,
                               body=self.response_body)

        Handler.do_GET = do_GET
        request = copy.deepcopy(self.request)

        self.assertRaises(CreationException, commands.selenium_status,
                          request, self.session, self.webdriver_server.port)


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

    def test_platform(self):
        from vmmaster.webdriver import commands

        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc["platform"], unicode)
        self.assertEqual(self.body["desiredCapabilities"]["platform"],
                         dc["platform"])

    def test_name(self):
        from vmmaster.webdriver import commands

        self.body['desiredCapabilities'].update({
            "name": "some_name"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)

        dc = commands.get_desired_capabilities(self.request)
        self.assertIsInstance(dc["name"], unicode)
        self.assertEqual(self.body["desiredCapabilities"]["name"], dc["name"])

    def test_no_name(self):
        from vmmaster.webdriver import commands

        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertEqual(dc.get("name", None), None)

    def test_take_screenshot_bool(self):
        from vmmaster.webdriver import commands

        self.body['desiredCapabilities'].update({
            "takeScreenshot": True
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertTrue(dc["takeScreenshot"])

    def test_take_screenshot_some_string(self):
        from vmmaster.webdriver import commands

        self.body['desiredCapabilities'].update({
            "takeScreenshot": "asdf"
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertTrue(dc["takeScreenshot"])

    def test_take_screenshot_empty_string(self):
        from vmmaster.webdriver import commands

        self.body['desiredCapabilities'].update({
            "takeScreenshot": ""
        })
        self.session_request_headers = {
            'content-length': '%s' % len(self.body),
        }
        self.request.headers.update(self.session_request_headers)
        self.request.body = json.dumps(self.body)
        dc = commands.get_desired_capabilities(self.request)
        self.assertFalse(dc["takeScreenshot"])


class TestRunScript(CommonCommandsTestCase):
    def setUp(self):
        super(TestRunScript, self).setUp()
        config.VMMASTER_AGENT_PORT = self.vmmaster_agent.port
        self.response_body = "some_body"

    def tearDown(self):
        super(TestRunScript, self).tearDown()

    def test_run_script(self):
        from vmmaster.webdriver import commands

        def run_script_through_websocket_mock(*args, **kwargs):
            return 200, {}, 'some_body'

        commands.run_script_through_websocket = \
            run_script_through_websocket_mock
        response = commands.run_script(self.request, self.session)

        self.assertEqual(200, response[0])
        self.assertEqual(self.response_body, response[2])


class TestLabelCommands(CommonCommandsTestCase):
    def test_label(self):
        from vmmaster.webdriver import commands

        request = copy.deepcopy(self.request)
        label = "step-label"
        request.body = json.dumps({"label": label})
        status, headers, body = commands.vmmaster_label(request, self.session)
        self.assertEqual(status, 200)
        json_body = json.loads(body)
        self.assertEqual(json_body["value"], label)
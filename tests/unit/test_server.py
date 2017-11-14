# coding: utf-8

import json
import time
from multiprocessing.pool import ThreadPool

from mock import Mock, patch
from uuid import uuid4
from core.config import setup_config, config
from tests.helpers import server_is_up, server_is_down, \
    new_session_request, get_session_request, delete_session_request, \
    vmmaster_label, run_script, BaseTestCase, \
    DatabaseMock, custom_wait, request_mock, wait_for

from nose.twistedtools import reactor


def ping_vm_true_mock(arg=None, ports=None):
    yield True


def selenium_status_true_mock(arg=None, arg2=None, arg3=None):
    yield 200, {}, ""


def ping_vm_false_mock(arg=None, ports=None):
    yield False


def transparent_mock():
    return 200, {}, None


class BaseTestFlaskApp(BaseTestCase):
    def setUp(self):
        with patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ), patch(
            'vmpool.virtual_machines_pool.VirtualMachinesPool', Mock()
        ):
            from vmmaster.app import create_app
            self.app = create_app()
            self.app.get_matched_platforms = Mock(return_value=('origin_1', 1))

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }


@patch.multiple(
    'vmmaster.webdriver.commands',
    ping_vm=Mock(side_effect=ping_vm_true_mock),
    selenium_status=Mock(return_value=(200, {}, json.dumps({'status': 0}))),
    start_selenium_session=Mock(return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch.multiple(
    "core.db.models.Session",
    endpoint_id=Mock(return_value=1),
    endpoint=Mock(
        vnc_port=5900,
        agent_port=9000,
        selenium_port=4455,
        _get_nova_client=Mock(return_value=Mock()),
        _wait_for_activated_service=custom_wait,
        ping_vm=Mock(return_value=True),
        is_broken=Mock(return_value=False)
    )
)
class TestServer(BaseTestFlaskApp):
    def setUp(self):
        setup_config('data/config_openstack.py')
        super(TestServer, self).setUp()

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }
        self.vmmaster_client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.app.cleanup()
        self.ctx.pop()

    def test_server_create_new_session(self):
        response = new_session_request(self.vmmaster_client, self.desired_caps)
        self.assertEqual(200, response.status_code)

    def test_server_creating_a_few_parallel_sessions(self):
        tpool = ThreadPool(2)

        deffered1 = tpool.apply_async(new_session_request, args=(
                self.vmmaster_client, self.desired_caps))
        deffered2 = tpool.apply_async(new_session_request, args=(
                self.vmmaster_client, self.desired_caps))
        deffered1.wait()
        deffered2.wait()
        result1 = deffered1.get()
        result2 = deffered2.get()
        self.assertEqual([result1.status_code, result2.status_code].count(200), 2)

    @patch('core.db.models.Session.set_user', Mock())
    def test_server_create_new_session_with_user_and_token(self):
        """
        - pass user and token via desired capabilities
        Expected: session created
        """

        _desired_caps = self.desired_caps.copy()
        _desired_caps["desiredCapabilities"]["user"] = "anonymous"
        _desired_caps["desiredCapabilities"]["token"] = None

        response = new_session_request(self.vmmaster_client, self.desired_caps)
        self.assertEqual(200, response.status_code)

    def test_get_non_existing_session(self):
        """
        - try to get session from empty pool
        Expected: exception
        """
        session_id = uuid4()
        with patch(
            'flask.current_app.database.get_session', Mock(return_value=None)
        ):
            response = get_session_request(self.vmmaster_client, session_id)
        self.assertTrue(
            "SessionException: There is no active session %s (Unknown session)"
            % session_id in response.data
        )

    def test_get_closed_session(self):
        """
        - succeed existing session
        - try to get this session
        Expected: session exception without any reason
        """
        from core.db.models import Session
        session = Session('some_platform')
        session.selenium_session = '1'
        session.succeed()

        with patch(
            'flask.current_app.database.get_session',
            Mock(return_value=session)
        ):
            response = get_session_request(self.vmmaster_client, session.id)
        self.assertIn(
            "SessionException: There is no active session %s"
            % session.id, response.data
        )
        session.close()

    def test_get_timeouted_session(self):
        """
        - timeout existing session
        - try to get this session
        Expected: session exception with reason 'Session timeout'
        """
        from core.db.models import Session
        session = Session('some_platform')
        session.selenium_session = '1'
        session.timeout()

        with patch(
            'flask.current_app.database.get_session',
            Mock(return_value=session)
        ):
            response = get_session_request(self.vmmaster_client, session.id)
        self.assertIn(
            "SessionException: There is no active session %s"
            % session.id, response.data
        )
        self.assertIn(
            "Session timeout. No activity since", response.data
        )
        session.close()

    @patch(
        'core.db.models.Session.make_request',
        Mock(side_effect=Mock(return_value=(200, {}, None)))
    )
    @patch(
        'vmmaster.webdriver.helpers.transparent',
        Mock(side_effect=transparent_mock)
    )
    def test_delete_session(self):
        """
        - create new session
        - try to get id from response
        - delete session by id
        Expected: session deleted
        """
        from core.db.models import Session
        session = Session('some_platform')
        session.succeed = Mock()
        session.add_session_step = Mock()

        with patch('flask.current_app.sessions.get_session',
                   Mock(return_value=session)):
            response = delete_session_request(self.vmmaster_client, session.id)
            session.succeed.assert_called_once_with()
        self.assertEqual(200, response.status_code)
        session.close()

    @patch(
        'core.db.models.Session.make_request',
        Mock(side_effect=Mock(return_value=(200, {}, None)))
    )
    @patch(
        'vmmaster.webdriver.helpers.transparent',
        Mock(side_effect=transparent_mock)
    )
    def test_delete_session_if_got_session_but_session_not_exist(self):
        """
        - create new session
        - try to get id from response
        - delete session by id
        - mocking get_session
        - repeat deleting session
        Expected: session deleted
        """
        from core.db.models import Session
        session = Session('some_platform')
        session.succeed = Mock()
        session.add_session_step = Mock()

        with patch(
            'core.sessions.Sessions.get_session',
            Mock(return_value=session)
        ):
            response = delete_session_request(self.vmmaster_client, session.id)
            self.assertEqual(200, response.status_code)
            response2 = delete_session_request(self.vmmaster_client, session.id)
            self.assertEqual(200, response2.status_code)
        session.close()

    @patch(
        'vmmaster.webdriver.helpers.is_request_closed',
        Mock(return_result=True)
    )
    def test_server_deleting_session_on_client_connection_drop(self):
        """
        - create vmmaster session
        - close the connection
        - try to get vmmaster session
        Expected: vmmaster session deleted
        """
        from core.db.models import Session
        session = Session('some_platform')
        with patch(
            'core.sessions.Sessions.get_session', Mock(return_value=session)
        ), patch.object(
            Session, 'close'
        ) as mock:
            get_session_request(self.vmmaster_client, session.id)

            self.assertTrue(mock.called)
            session.close()

    @patch('flask.current_app.database.get_session', Mock(return_value=None))
    def test_delete_non_existing_session(self):
        """
        - try to delete session from empty pool
        Expected: exception
        """
        session_id = uuid4()
        response = delete_session_request(self.vmmaster_client, session_id)
        self.assertTrue(
            "SessionException: There is no active session %s (Unknown session)"
            % session_id in response.data
        )

    @patch(
        'vmmaster.webdriver.commands.AgentCommands',
        {'runScript': Mock(return_value=(200, {}, json.dumps({"output": "hello world\n"})))}
    )
    def test_run_script(self):
        """
        - create vmmaster session
        - send run_script request
        Expected: script executed, output contains echo message
        """
        from core.db.models import Session
        session = Session('some_platform')
        session.selenium_session = '1'
        output = json.dumps({"output": "hello world\n"})

        with patch(
            'core.sessions.Sessions.get_session',
            Mock(return_value=session)
        ):
            response = run_script(
                self.vmmaster_client, session.id, "echo 'hello world'")

        self.assertEqual(200, response.status_code)
        self.assertEqual(output, response.data)
        session.close()

    @patch(
        'vmmaster.webdriver.commands.InternalCommands',
        {'vmmasterLabel': Mock(return_value=(200, {}, json.dumps({"value": "step-label"})))}
    )
    def test_vmmaster_label(self):
        from core.db.models import Session
        session = Session('some_platform')
        with patch(
            'core.sessions.Sessions.get_session', Mock(return_value=session)
        ):
            response = vmmaster_label(self.vmmaster_client, session.id, "step-label")

        self.assertEqual(200, response.status_code)
        self.assertEqual(json.dumps({"value": "step-label"}), response.data)
        session.close()

    @patch('vmmaster.webdriver.helpers.swap_session', Mock())
    def test_vmmaster_no_such_platform(self):
        self.app.get_matched_platforms = Mock(return_value=(None, None))
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.vmmaster_client, desired_caps)
        error = json.loads(response.data).get('value').get('message')

        self.assertIn('Cannot match platform for DesiredCapabilities: {u\'platform\': u\'no_platform\'}', error)


class TestSessionWorker(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')

        from flask import Flask
        self.app = Flask(__name__)
        self.app.sessions = Mock()
        self.app.sessions.app = self.app

        from core.sessions import SessionWorker
        self.worker = SessionWorker(self.app.sessions)

    def tearDown(self):
        self.worker.stop()

    def test_server_timeouted_session(self):
        """
        - create timeouted session
        - run session worker
        Expected: session timeouted
        """

        session = Mock()
        session.timeout = Mock()
        session.is_active = False
        session.inactivity = config.SESSION_TIMEOUT + 1

        self.app.sessions.running = Mock(return_value=[session])
        self.worker.start()
        time.sleep(1)
        session.timeout.assert_any_call()
        session.close()


class TestConnectionClose(BaseTestFlaskApp):
    def setUp(self):
        setup_config('data/config_openstack.py')
        super(TestConnectionClose, self).setUp()

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }
        self.vmmaster_client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.app.cleanup()
        self.ctx.pop()

    def test_req_closed_during_session_creating(self):
        """
        - close the connection when the session was created
        Expected: session deleted, vm deleted
        """
        with patch(
            'vmmaster.webdriver.helpers.is_request_closed', Mock(return_value=True)
        ):
            response = new_session_request(self.vmmaster_client, self.desired_caps)
            self.assertEqual(response.status_code, 500)
            self.assertIn("ConnectionError: Client has disconnected", response.data)


class TestServerShutdown(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.address = ("localhost", config.PORT)

        with patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ), patch(
            'vmpool.virtual_machines_pool.VirtualMachinesPool', Mock()
        ):
            from vmmaster.server import VMMasterServer
            self.vmmaster = VMMasterServer(reactor, config.PORT)

            self.assertTrue(server_is_up(self.address))

    def tearDown(self):
        self.vmmaster.stop_services()
        self.assertTrue(server_is_down(self.address))

    def test_server_stop_port_listening(self):
        """
        - send SIGTERM to reactor
        Expected: server is down, port free, reactor stopped
        """
        self.vmmaster.reactor.sigTerm()
        self.assertTrue(server_is_down(self.address, wait=10))
        self.assertTrue(self.vmmaster.reactor._stopped)

    def test_session_wait_for_active_sessions(self):
        """
        Test all sessions completed before shutdown
            - send SIGTERM to reactor
            - all sessions still not closed
            - server is up
            - finish all sessions
            - check server is down
        Expected: server not stopped while sessions are active
        """
        sessions = [Mock(is_done=False)] * 5

        with patch('core.sessions.Sessions.active', Mock(return_value=sessions)):
            self.vmmaster._wait_for_end_active_sessions = True
            self.vmmaster.reactor.sigTerm()

            self.assertFalse(any([session.close.called for session in sessions]))
            self.assertTrue(server_is_up(self.address))

            for session in sessions:
                session.is_done = True

        self.assertTrue(server_is_down(self.address, wait=10))
        self.assertTrue(self.vmmaster.reactor._stopped)

    def test_server_kill_all_active_sessions(self):
        """
        Test all active sessions closed while shutdown
        Expected: all sessions has been stopped, port free, reactor stopped
        """
        sessions = [Mock(is_done=False)] * 5

        with patch('core.sessions.Sessions.active', Mock(return_value=sessions)):
            self.vmmaster.reactor.sigTerm()
            self.assertTrue(wait_for(lambda: all([session.close.called for session in sessions])))

        self.assertTrue(server_is_down(self.address))
        self.assertTrue(self.vmmaster.reactor._stopped)


@patch.multiple(
    "core.db.models.Session",
    endpoint_id=Mock(return_value=1),
    endpoint=Mock(
        vnc_port=5900,
        agent_port=9000,
        selenium_port=4455,
        _get_nova_client=Mock(return_value=Mock()),
        _wait_for_activated_service=custom_wait,
        ping_vm=Mock(return_value=True),
        is_broken=Mock(return_value=False)
    )
)
@patch('vmmaster.webdriver.helpers.swap_session', Mock())
class TestSessionSteps(BaseTestFlaskApp):
    def setUp(self):
        setup_config('data/config_openstack.py')
        super(TestSessionSteps, self).setUp()
        self.vmmaster_client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.app.cleanup()
        self.ctx.pop()

    @patch.multiple(
        'vmmaster.webdriver.commands',
        ping_vm=Mock(side_effect=ping_vm_true_mock),
        selenium_status=Mock(return_value=(200, {}, json.dumps({'status': 0})))
    )
    def test_add_first_two_steps(self):
        """
        - exception while waiting endpoint
        Expected: session was created, session_step was created
        """

        def raise_exception():
            raise Exception('something ugly happened in get_vm')

        with patch(
            'core.db.models.Session.restore', Mock(side_effect=raise_exception)
        ), patch(
            'core.db.models.Session.add_session_step', Mock()
        ) as add_step_mock:
            response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(500, response.status_code)
        self.assertIn('something ugly happened in get_vm', response.data)

        self.assertTrue(add_step_mock.called)

    @patch.multiple(
        'vmmaster.webdriver.commands',
        ping_vm=Mock(side_effect=ping_vm_true_mock),
        selenium_status=Mock(return_value=(200, {}, json.dumps({'status': 0})))
    )
    def test_always_create_response_for_sub_step(self):
        """
        - exception while executing make_request
        Expected: session failed, sub_steps was created
        """

        def raise_exception(*args, **kwargs):
            raise Exception('something ugly happened in make_request')

        with patch(
            'core.db.models.Session.endpoint_id', Mock(return_value=1)
        ), patch(
            'core.db.models.Session.make_request',
            Mock(__name__="make_request", side_effect=raise_exception)
        ), patch(
            'core.db.models.Session.add_sub_step', Mock()
        ) as add_sub_step_mock:
            response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(500, response.status_code)
        self.assertIn('something ugly happened in make_request', response.data)

        self.assertEqual(add_sub_step_mock.call_count, 2)


@patch.multiple(
    "core.db.models.Session",
    endpoint_id=Mock(return_value=1),
    endpoint=Mock(
        vnc_port=5900,
        agent_port=9000,
        selenium_port=4455,
        _get_nova_client=Mock(return_value=Mock()),
        _wait_for_activated_service=custom_wait,
        ping_vm=Mock(return_value=True),
        is_broken=Mock(return_value=False)
    )
)
class TestRunScriptTimeGreaterThenSessionTimeout(BaseTestFlaskApp):
    def setUp(self):
        setup_config('data/config_openstack.py')
        super(TestRunScriptTimeGreaterThenSessionTimeout, self).setUp()
        self.vmmaster_client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.app.cleanup()
        self.ctx.pop()

    @patch.multiple(
        'vmmaster.webdriver.commands',
        ping_vm=Mock(side_effect=ping_vm_true_mock),
        selenium_status=Mock(side_effect=selenium_status_true_mock),
        start_selenium_session=Mock(return_value=(200, {}, json.dumps({'sessionId': 1}))),
    )
    @patch('flask.current_app.database', Mock(get_session=Mock(return_value=None)))
    @patch('requests.request', Mock(side_effect=request_mock))
    def test_check_timer_for_session_activity(self):
        """
        - exception while waiting endpoint
        Expected: session was created, session_step was created
        """
        response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(200, response.status_code, response.data)

        response = get_session_request(self.vmmaster_client, 1)
        self.assertIn(
            "SessionException: There is no active session 1 (Unknown session)",
            response.data
        )

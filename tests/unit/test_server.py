# coding: utf-8

import json
import time
from threading import Thread
from multiprocessing.pool import ThreadPool
from twisted.internet import defer

from mock import Mock, patch, PropertyMock
from uuid import uuid4
from core.config import setup_config, config
from tests.unit.helpers import server_is_up, server_is_down, \
    new_session_request, get_session_request, delete_session_request, \
    vmmaster_label, run_script, request_with_drop, BaseTestCase, \
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


@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
class BaseTestFlaskApp(BaseTestCase):
    def setUp(self):
        self.mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1,
            short_name="origin_1"
        )
        type(self.mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'core.video.VNCVideoHelper', Mock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ), patch(
            'core.sessions.Session.save_artifacts', Mock()
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
        ):
            from vmmaster.app import create_app
            self.app = create_app()

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.app.pool.platforms.platforms.keys()[0]
            }
        }


@patch.multiple(
    'vmmaster.webdriver.commands',
    ping_vm=Mock(side_effect=ping_vm_true_mock),
    selenium_status=Mock(return_value=(200, {}, json.dumps({'status': 0}))),
    start_selenium_session=Mock(return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch.multiple(
    "vmpool.clone.OpenstackClone",
    vnc_port=5900,
    agent_port=9000,
    selenium_port=4455,
    _get_nova_client=Mock(return_value=Mock()),
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True),
    is_broken=Mock(return_value=False),
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

        vm_count = len(self.app.pool.using)
        self.assertEqual(1, vm_count)

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

        vm_count = len(self.app.pool.using)

        self.assertEqual([result1.status_code, result2.status_code].count(200), 2)
        self.assertEqual(2, vm_count)

    @patch('core.sessions.Session.set_user', Mock())
    def test_server_create_new_session_with_user_and_token(self):
        """
        - pass user and token via desired capabilities
        Expected: session created
        """

        _desired_caps = self.desired_caps.copy()
        _desired_caps["desiredCapabilities"]["user"] = "anonymous"
        _desired_caps["desiredCapabilities"]["token"] = None

        response = new_session_request(self.vmmaster_client, self.desired_caps)

        vm_count = len(self.app.pool.using)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, vm_count)

    def test_server_maximum_vm_running(self):
        """
        - maximum machines in pool
        - try to create new session
        Expected: thread with new session is alive
        """

        self.app.pool.add('origin_1')
        self.app.pool.add('origin_1')

        t = Thread(
            target=new_session_request,
            args=(self.vmmaster_client, self.desired_caps)
        )
        t.daemon = True
        t.start()
        self.assertEqual(2, len(self.app.pool.using))
        self.assertTrue(t.isAlive())
        t.join(1)

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
        from core.sessions import Session
        session = Session()
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
        from core.sessions import Session
        session = Session()
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
        'core.sessions.Session.make_request',
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
        from core.sessions import Session
        session = Session()
        session.succeed = Mock()
        session.add_session_step = Mock()

        with patch('flask.current_app.sessions.get_session',
                   Mock(return_value=session)):
            response = delete_session_request(self.vmmaster_client, session.id)
            session.succeed.assert_called_once_with()
        self.assertEqual(200, response.status_code)
        session.close()

    @patch(
        'core.sessions.Session.make_request',
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
        from core.sessions import Session
        session = Session()
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
        from core.sessions import Session
        session = Session()
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
        from core.sessions import Session
        session = Session()
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
        from core.sessions import Session
        session = Session()
        with patch(
            'core.sessions.Sessions.get_session', Mock(return_value=session)
        ):
            response = vmmaster_label(self.vmmaster_client, session.id, "step-label")

        self.assertEqual(200, response.status_code)
        self.assertEqual(json.dumps({"value": "step-label"}), response.data)
        session.close()

    @patch('vmmaster.webdriver.helpers.swap_session', Mock())
    def test_vmmaster_no_such_platform(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.vmmaster_client, desired_caps)
        error = json.loads(response.data).get('value').get('message')

        self.assertIn('PlatformException: No such platform no_platform', error)


@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
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


@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
@patch.multiple(
    "vmpool.clone.OpenstackClone",
    vnc_port=5900,
    agent_port=9000,
    selenium_port=4455,
    _get_nova_client=Mock(return_value=Mock()),
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True),
    is_broken=Mock(return_value=False),
)
class TestConnectionClose(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.address = ("localhost", config.PORT)
        mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1,
            short_name="origin_1"
        )
        type(mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'core.video.VNCVideoHelper', Mock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ), patch(
            'core.sessions.Session.save_artifacts', Mock()
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
        ):
            from vmmaster.server import VMMasterServer
            self.vmmaster = VMMasterServer(reactor, config.PORT)

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.vmmaster.app.pool.platforms.platforms.keys()[0]
            }
        }

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

    @defer.inlineCallbacks
    def tearDown(self):
        self.vmmaster.app.sessions.kill_all()
        yield self.vmmaster.stop_services()
        self.ctx.pop()
        server_is_down(self.address)

    def test_req_closed_during_session_creating(self):
        """
        - close the connection when the session was created
        Expected: session deleted, vm deleted
        """
        def pool_fake_return():
            time.sleep(2)
            return Mock()

        self.assertEqual(0, self.vmmaster.app.pool.count())

        with patch(
            'flask.current_app.pool.has', Mock(side_effect=pool_fake_return)
        ):
            request_with_drop(self.address, self.desired_caps, None)

        self.assertEqual(0, self.vmmaster.app.pool.count())

    def test_req_closed_when_request_append_to_queue(self):
        """
        - close the connection when the request is queued
        Expected: session deleted, vm deleted
        """
        with patch(
            'flask.current_app.pool.has', Mock(return_value=False)
        ), patch(
            'flask.current_app.pool.can_produce', Mock(return_value=False)
        ):
            request_with_drop(self.address, self.desired_caps, None)

        self.assertEqual(0, self.vmmaster.app.pool.count())

    def test_req_closed_when_platform_queued(self):
        """
        - wait until platform is queued
        - check queue state
        - drop request while platform is queued
        Expected: platform no more in queue
        """
        with patch(
            'flask.current_app.pool.has', Mock(return_value=False)
        ), patch(
            'flask.current_app.pool.can_produce', Mock(return_value=True)
        ):
            q = self.vmmaster.app.sessions.active_sessions

            def wait_for_platform_in_queue():
                wait_for(lambda: q, timeout=2)
                self.assertEqual(len(q), 1)

                self.assertEqual(
                    self.vmmaster.app.sessions.active()[0].dc,
                    json.dumps(self.desired_caps["desiredCapabilities"])
                )

            request_with_drop(
                self.address, self.desired_caps, wait_for_platform_in_queue
            )
            wait_for(lambda: not q, timeout=2)
            self.assertEqual(len(q), 0)

    def test_req_closed_when_vm_is_spawning(self):
        """
        - waiting for clone spawning to begin
        - drop request while vm is spawning
        Expected: queue is empty, vm spawned and then deleted
        """

        vm_mock = Mock()
        vm_mock.delete = Mock()
        vm_mock.save_artifacts = Mock(return_value=False)

        def just_sleep(*args, **kwargs):
            time.sleep(2)
            return vm_mock

        with patch(
            'flask.current_app.pool.has', Mock(return_value=False)
        ), patch(
            'flask.current_app.pool.can_produce', Mock(return_value=True)
        ), patch(
            'vmpool.platforms.OpenstackOrigin.make_clone', Mock(side_effect=just_sleep)
        ) as make_clone:
            q = self.vmmaster.app.sessions.active_sessions

            def wait_for_vm_start_tp_spawn():
                wait_for(lambda: make_clone.called, timeout=10)
                self.assertTrue(make_clone.called)
                self.assertEqual(len(q), 1)

            request_with_drop(
                self.address, self.desired_caps, wait_for_vm_start_tp_spawn
            )

            wait_for(lambda: not q, timeout=10)
            self.assertEqual(len(q), 0)

        wait_for(lambda: vm_mock.delete.called)
        vm_mock.delete.assert_any_call()


@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
class TestServerShutdown(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.address = ("localhost", config.PORT)
        mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1,
            short_name="origin_1"
        )
        type(mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch(
                'core.db.Database', DatabaseMock()
        ), patch(
            'core.video.VNCVideoHelper', Mock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ), patch(
            'core.sessions.Session.save_artifacts', Mock()
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
        ):
            from vmmaster.server import VMMasterServer
            self.vmmaster = VMMasterServer(reactor, config.PORT)

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @defer.inlineCallbacks
    def test_server_shutdown(self):
        """
        - shutdown current instance
        Expected: server is down
        """
        yield self.vmmaster.stop_services()
        with self.assertRaises(RuntimeError):
            server_is_up(self.address, wait=1)

    @defer.inlineCallbacks
    def test_session_is_not_deleted_after_server_shutdown(self):
        """
        - delete server with active session
        Expected: session not deleted
        """
        from core.sessions import Session
        session = Session()
        session.closed = False

        with patch('core.sessions.Sessions.get_session', Mock(return_value=session)):
            yield self.vmmaster.stop_services()

        self.assertTrue(session.closed)
        session.failed()

        server_is_down(self.address)


@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
@patch.multiple(
    'vmmaster.webdriver.commands',
    ping_vm=Mock(side_effect=ping_vm_true_mock),
    selenium_status=Mock(return_value=(200, {}, json.dumps({'status': 0}))),
    start_selenium_session=Mock(return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch.multiple(
    "vmpool.clone.OpenstackClone",
    vnc_port=5900,
    agent_port=9000,
    selenium_port=4455,
    _get_nova_client=Mock(return_value=Mock()),
    _wait_for_activated_service=custom_wait,
    is_broken=Mock(return_value=False),
)
class TestServerWithPreloadedVM(BaseTestFlaskApp):
    def setUp(self):
        setup_config('data/config_with_preloaded.py')

        super(TestServerWithPreloadedVM, self).setUp()

        self.vmmaster_client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.app.cleanup()
        self.ctx.pop()

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        is_created=Mock(return_value=True),
        ping_vm=Mock(side_effect=ping_vm_true_mock)
    )
    def test_max_count_with_run_new_request_during_prevm_is_ready(self):
        """
        - wait while preloaded is ready
        - make new session request
        Expected: session created
        """
        while True:
            if len(self.app.pool.pool):
                if self.app.pool.pool[0].ready:
                    break

        response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, self.app.pool.count())

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        is_created=Mock(return_value=False),
        ping_vm=Mock(side_effect=ping_vm_false_mock)
    )
    def test_max_count_with_run_new_request_during_prevm_is_not_ready(self):
        """
        - do not wait for preloaded vm ready status
        - make new session request
        Expected: session created
        """
        response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, self.app.pool.count())


@patch.multiple(
    "vmpool.clone.OpenstackClone",
    vnc_port=5900,
    agent_port=9000,
    selenium_port=4455,
    _get_nova_client=Mock(return_value=Mock()),
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True),
    is_broken=Mock(return_value=False),
)
@patch('vmmaster.webdriver.helpers.swap_session', Mock())
@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
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

    def test_add_first_two_steps(self):
        """
        - exception while waiting endpoint
        Expected: session was created, session_step was created
        """

        def raise_exception(dc):
            raise Exception('something ugly happened in get_vm')

        with patch(
            'vmpool.endpoint.get_vm', Mock(side_effect=raise_exception)
        ), patch(
            'core.sessions.Session.save_artifacts', Mock(return_value=False),
        ), patch(
            'core.sessions.Session.add_session_step', Mock()
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

        def new_vm_mock(arg):
            yield Mock(ip=1)

        with patch(
            'vmpool.endpoint.get_vm', Mock(side_effect=new_vm_mock)
        ), patch(
            'core.sessions.Session.make_request',
            Mock(__name__="make_request", side_effect=raise_exception)
        ), patch(
            'core.sessions.Session.add_sub_step', Mock()
        ) as add_sub_step_mock:
            response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(500, response.status_code)
        self.assertIn(
            'something ugly happened in make_request', response.data)

        self.assertEqual(add_sub_step_mock.call_count, 2)


@patch.multiple(
    "vmpool.clone.OpenstackClone",
    vnc_port=5900,
    agent_port=9000,
    selenium_port=4455,
    _get_nova_client=Mock(return_value=Mock()),
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True),
    is_broken=Mock(return_value=False),
)
@patch('core.utils.openstack_utils.nova_client', Mock(return_value=Mock()))
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
        def get_vm_mock(arg):
            yield Mock(name="test_vm_1", ip="127.0.0.1")

        with patch(
            'vmpool.endpoint.get_vm', Mock(side_effect=get_vm_mock)
        ):
            response = new_session_request(self.vmmaster_client, self.desired_caps)

        self.assertEqual(200, response.status_code)

        response = get_session_request(self.vmmaster_client, 1)
        self.assertIn(
            "SessionException: There is no active session 1 (Unknown session)",
            response.data
        )

# coding: utf-8

import json
import time

from mock import Mock, patch, PropertyMock
from uuid import uuid4
from threading import Thread
from multiprocessing.pool import ThreadPool
from core.config import setup_config, config
from tests.unit.helpers import server_is_up, server_is_down, \
    new_session_request, get_session_request, delete_session_request, \
    vmmaster_label, run_script, request_with_drop, BaseTestCase, \
    set_primary_key, DatabaseMock


from nose.twistedtools import reactor


class BaseTestServer(BaseTestCase):
    def setUp(self):
        with patch(
            'core.connection.Virsh', Mock(),
        ), patch(
            'core.network.Network', Mock()
        ), patch(
            'core.db.database', DatabaseMock()
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ):
            from vmmaster.server import VMMasterServer
            self.vmmaster = VMMasterServer(reactor, self.address[1])

        self.pool = self.vmmaster.app.pool

        server_is_up(self.address)


def ping_vm_true_mock(arg=None):
    yield True


def ping_vm_false_mock(arg=None):
    yield False


def transparent_mock():
    return 200, {}, None


@patch.multiple(
    "vmpool.clone.KVMClone",
    clone_origin=Mock(),
    define_clone=Mock(),
    start_virtual_machine=Mock(),
    drive_path=Mock()
)
@patch(
    'vmmaster.webdriver.commands.ping_vm',
    new=Mock(side_effect=ping_vm_true_mock)
)
@patch(
    'vmmaster.webdriver.commands.selenium_status',
    new=Mock(
        __name__="selenium_status",
        return_value=(200, {}, json.dumps({'status': 0}))
    )
)
@patch(
    'vmmaster.webdriver.commands.start_selenium_session',
    new=Mock(
        __name__="start_selenium_session",
        return_value=(200, {}, json.dumps({'sessionId': "1"}))
    )
)
class TestServer(BaseTestServer):
    def setUp(self):
        setup_config('data/config.py')

        self.address = ("localhost", 9001)

        super(TestServer, self).setUp()

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'test_origin_1'
            }
        }

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

    @patch('core.utils.delete_file', Mock())
    def tearDown(self):
        self.vmmaster.app.sessions.kill_all()
        self.ctx.pop()
        del self.vmmaster
        server_is_down(self.address)

    def test_server_create_new_session(self):
        response = new_session_request(self.address, self.desired_caps)

        vm_count = len(self.pool.using)

        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    def test_server_creating_a_few_parallel_sessions(self):
        tpool = ThreadPool(3)

        deffered1 = tpool.apply_async(new_session_request, args=(
            self.address, self.desired_caps))
        deffered2 = tpool.apply_async(new_session_request, args=(
            self.address, self.desired_caps))
        deffered3 = tpool.apply_async(new_session_request, args=(
            self.address, self.desired_caps))
        deffered1.wait()
        deffered2.wait()
        deffered3.wait()
        result1 = deffered1.get()
        result2 = deffered2.get()
        result3 = deffered3.get()

        vm_count = len(self.pool.using)

        self.assertTrue(
            [result1.status, result2.status, result3.status].count(200) == 2)
        self.assertTrue(
            500 in (result1.status, result2.status, result3.status))
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

        response = new_session_request(self.address, _desired_caps)

        vm_count = len(self.pool.using)

        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    def test_server_maximum_vm_running(self):
        """
        - maximum machines in pool
        - try to create new session
        Expected: thread with new session is alive
        """

        self.pool.add('test_origin_1')
        self.pool.add('test_origin_1')

        t = Thread(
            target=new_session_request,
            args=(self.address, self.desired_caps)
        )
        t.daemon = True
        t.start()
        self.assertEqual(2, len(self.pool.using))
        self.assertTrue(t.isAlive())
        t.join(0.1)

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
            response = delete_session_request(self.address, session.id)
            session.succeed.assert_called_once_with()
        self.assertEqual(200, response.status)
        session.delete()

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
            response = delete_session_request(self.address, session.id)
            self.assertEqual(200, response.status)
            response2 = delete_session_request(self.address, session.id)
            self.assertEqual(200, response2.status)
        session.delete()

    @patch('flask.current_app.database.get_session', Mock(return_value=None))
    def test_delete_none_existing_session(self):
        """
        - try to delete session from empty pool
        Expected: exception
        """
        session_id = uuid4()
        response = delete_session_request(self.address, session_id)
        self.assertTrue("SessionException: There is no active session %s" %
                        session_id in response.content)

    def test_get_none_existing_session(self):
        """
        - try to get session from empty pool
        Expected: exception
        """
        session_id = uuid4()
        response = get_session_request(self.address, session_id)
        self.assertTrue("SessionException: There is no active session %s" %
                        session_id in response.content)

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
            'core.sessions.Sessions.get_session',
            Mock(return_value=session)
        ), patch.object(
            Session, 'delete'
        ) as mock:
            get_session_request(self.address, session.id)

        self.assertTrue(mock.called)
        session.delete()

    @patch(
        'vmmaster.webdriver.commands.AgentCommands',
        {'runScript': Mock(
            return_value=(200, {}, json.dumps({"output": "hello world\n"})))}
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
                self.address, session.id, "echo 'hello world'")

        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)
        session.delete()

    @patch(
        'vmmaster.webdriver.commands.InternalCommands',
        {'vmmasterLabel': Mock(
            return_value=(200, {}, json.dumps({"value": "step-label"})))}
    )
    def test_vmmaster_label(self):
        from core.sessions import Session
        session = Session()
        with patch(
            'core.sessions.Sessions.get_session', Mock(return_value=session)
        ):
            response = vmmaster_label(self.address, session.id, "step-label")

        self.assertEqual(200, response.status)
        self.assertEqual(json.dumps({"value": "step-label"}), response.content)
        session.delete()

    def test_vmmaster_no_such_platform(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.address, desired_caps)
        error = json.loads(response.content).get('value').get('message')

        self.assertIn('PlatformException: No such platform no_platform', error)


class TestSessionWorker(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')

        from flask import Flask
        self.app = Flask(__name__)

        with patch(
            'core.connection.Virsh', Mock(),
        ), patch(
            'core.network.Network', Mock()
        ):
            from core.sessions import SessionWorker
        self.worker = SessionWorker(self.app)

        self.app.sessions = Mock()

    def tearDown(self):
        self.worker.stop()
        del self.app

    def test_server_timeouted_session(self):
        """
        - create timeouted session
        - run session worker
        Expected: session timeouted
        """

        session = Mock()
        session.timeout = Mock()
        session.inactivity = config.SESSION_TIMEOUT + 1

        self.app.sessions.active = Mock(return_value=[session])
        self.worker.start()
        time.sleep(1)
        session.timeout.assert_any_call()
        session.delete()


class TestSessionStates(BaseTestServer):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)

        super(TestSessionStates, self).setUp()

        self.pool = self.vmmaster.app.pool

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.vmmaster.app.platforms.platforms.keys()[0]
            }
        }

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

    @patch('core.utils.delete_file', Mock())
    def tearDown(self):
        self.vmmaster.app.sessions.kill_all()
        self.ctx.pop()
        del self.vmmaster
        server_is_down(self.address)

    def test_server_get_closed_session(self):
        """
        - close existing session
        - try to get closed session
        Expected: session exception
        """
        from core.sessions import Session
        session = Session()
        session.selenium_session = '1'
        session.closed = True

        with patch('flask.current_app.sessions.active',
                   new=Mock(return_value=[session])):
            response = get_session_request(self.address, session.id)

        self.assertIn("SessionException: Session %s closed"
                      % session.id, response.content)
        session.delete()

    def test_req_closed_during_session_creating(self):
        """
        - close the connection when the session was created
        Expected: session deleted, vm deleted
        """
        def pool_fake_return():
            time.sleep(2)
            return Mock()

        self.assertEqual(0, self.pool.count())

        import vmpool.virtual_machines_pool as vmp
        with patch.object(vmp, 'pool', Mock()) as p:
            p.has = Mock(side_effect=pool_fake_return)
            request_with_drop(self.address, self.desired_caps, None)

        self.assertEqual(0, self.pool.count())

    def test_req_closed_when_request_append_to_queue(self):
        """
        - close the connection when the request is queued
        Expected: session deleted, vm deleted
        """
        import vmpool.virtual_machines_pool as vmp
        with patch.object(vmp, 'pool', Mock()) as p:
            p.has = Mock(return_value=False)
            p.can_produce = Mock(return_value=False)
            request_with_drop(self.address, self.desired_caps, None)

        self.assertEqual(0, self.pool.count())


class TestServerShutdown(BaseTestServer):
    def setUp(self):
        setup_config('data/config.py')

        self.address = ("localhost", 9001)

        super(TestServerShutdown, self).setUp()

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.vmmaster.app.platforms.platforms.keys()[0]
            }
        }

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_server_shutdown(self):
        """
        - shutdown current instance
        Expected: server is down
        """
        del self.vmmaster
        with self.assertRaises(RuntimeError):
            server_is_up(self.address, wait=1)

    def test_session_is_not_deleted_after_server_shutdown(self):
        """
        - delete server with active session
        Expected: session not deleted
        """
        from core.sessions import Session
        session = Session()
        session.closed = False

        with patch('core.sessions.Sessions.get_session',
                   Mock(return_value=session)):
            del self.vmmaster

        self.assertFalse(session.closed)
        session.failed()

        server_is_down(self.address)


def custom_wait(self, method):
    self.ready = True
    self.checking = False


@patch(
    'vmmaster.webdriver.commands.ping_vm',
    new=Mock(__name__="check_vm_online", side_effect=ping_vm_true_mock)
)
@patch(
    'vmmaster.webdriver.commands.selenium_status',
    new=Mock(
        __name__="selenium_status",
        return_value=(200, {}, json.dumps({'status': 0}))
    )
)
@patch(
    'vmmaster.webdriver.commands.start_selenium_session',
    new=Mock(
        __name__="start_selenium_session",
        return_value=(200, {}, json.dumps({'sessionId': "1"}))
    )
)
class TestServerWithPreloadedVM(BaseTestCase):
    def setUp(self):
        setup_config('data/config_with_preloaded.py')

        self.address = ("localhost", 9001)

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }

        mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'), min_disk=20,
            min_ram=2, instance_type_flavorid=1
        )
        type(mocked_image).name = PropertyMock(return_value='test_origin_1')

        with patch(
            'core.connection.Virsh', Mock(),
        ), patch(
            'core.network.Network', Mock()
        ), patch(
            'core.db.database', Mock(add=Mock(side_effect=set_primary_key))
        ), patch.multiple(
            'core.utils.openstack_utils',
            neutron_client=Mock(return_value=Mock()),
            glance_client=Mock(return_value=Mock()),
            nova_client=Mock(return_value=Mock())
        ), patch.multiple(
            'vmpool.clone.OpenstackClone',
            _wait_for_activated_service=custom_wait,
            get_network_id=Mock(return_value=1),
            get_network_name=Mock(return_value='Local-Net')
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}
            )
        ):
            from vmmaster.server import VMMasterServer
            self.vmmaster = VMMasterServer(reactor, self.address[1])

        self.pool = self.vmmaster.app.pool

        server_is_up(self.address)

    @patch('core.utils.delete_file', Mock())
    def tearDown(self):
        del self.vmmaster
        server_is_down(self.address)

    @patch('vmpool.clone.OpenstackClone.vm_has_created', new=Mock(
        __name__='vm_has_created',
        return_value=True
    ))
    @patch('vmpool.clone.OpenstackClone.ping_vm', new=Mock(
        __name__='ping_vm',
        side_effect=ping_vm_true_mock
    ))
    def test_max_count_with_run_new_request_during_prevm_is_ready(self):
        """
        - wait while preloaded is ready
        - make new session request
        Expected: session created
        """
        while True:
            if self.pool.pool[0].ready is True:
                break

        response = new_session_request(self.address, self.desired_caps)

        self.assertEqual(200, response.status)
        self.assertEqual(1, self.pool.count())

    @patch('vmpool.clone.OpenstackClone.vm_has_created', new=Mock(
        __name__='vm_has_created',
        return_value='False'
    ))
    @patch('vmpool.clone.OpenstackClone.ping_vm', new=Mock(
        __name__='ping_vm',
        side_effect=ping_vm_false_mock
    ))
    def test_max_count_with_run_new_request_during_prevm_is_not_ready(self):
        """
        - do not wait for preloaded vm ready status
        - make new session request
        Expected: session created
        """
        response = new_session_request(self.address, self.desired_caps)

        self.assertEqual(200, response.status)
        self.assertEqual(1, self.pool.count())

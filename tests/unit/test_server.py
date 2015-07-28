# coding: utf-8

import json
import time
from mock import Mock, patch, PropertyMock

from uuid import uuid4
from flask import Response
from vmmaster.core.config import setup_config, config
from helpers import server_is_up, server_is_down, \
    new_session_request, get_session_request, delete_session_request, \
    vmmaster_label, run_script, request_with_drop, fake_home_dir, BaseTestCase


def empty_decorator(f):
    return f


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="check_vm_online", return_value=True))
@patch('vmmaster.webdriver.commands.selenium_status', new=Mock(
    __name__="selenium_status",
    return_value=(200, {}, json.dumps({'status': 0})))
)
@patch('vmmaster.core.db.database', new=Mock())
class TestServer(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'test_origin_1'
            }
        }

        with patch('vmmaster.core.network.network.Network', Mock(
                return_value=Mock(get_ip=Mock(return_value='0')))), \
            patch('vmmaster.core.connection.Virsh', Mock()), \
                patch('vmmaster.core.db.database', Mock()), \
                patch('vmmaster.core.utils.init.home_dir',
                      Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      Mock(return_value=Mock())),\
                patch('vmmaster.core.sessions.SessionWorker', Mock()):

            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmmaster.server import VMMasterServer
            from vmpool.server import VMPool
            from nose.twistedtools import reactor
            self.vmmaster = VMMasterServer(reactor, self.address[1])
            self.vmpool = VMPool(reactor, self.vmpool_address[1])

        server_is_up(self.address)
        server_is_up(self.vmpool_address)

        # TODO: mock it via 'with patch'
        from vmmaster.core.utils import utils
        utils.delete_file = Mock()
        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()
        KVMClone.id = 1

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()):
            del self.vmmaster
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch.multiple('vmmaster.core.sessions.Session',
                    set_vm=Mock(),
                    endpoint_name=Mock(return_value='some_machine'))
    def test_server_create_new_session(self):
        with patch('vmmaster.core.sessions.Session.run_script',
                   PropertyMock(return_value=False)):
            response = new_session_request(self.address, self.desired_caps)

        from vmpool.virtual_machines_pool import pool
        vm_count = len(pool.using)

        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    @patch.multiple('vmmaster.core.sessions.Session',
                set_vm=Mock(),
                endpoint_name=Mock(return_value='some_machine'))
    def test_server_creating_a_few_parallel_sessions(self):
        from multiprocessing.pool import ThreadPool
        tpool = ThreadPool(3)
        with patch('vmmaster.core.sessions.Session.run_script',
                   PropertyMock(return_value=False)):
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

        from vmpool.virtual_machines_pool import pool
        vm_count = len(pool.using)

        self.assertTrue(
            200 in (result1.status, result2.status, result3.status))
        self.assertTrue(
            500 in (result1.status, result2.status, result3.status))
        self.assertEqual(2, vm_count)

    @patch.multiple('vmmaster.core.sessions.Session',
                    set_vm=Mock(),
                    set_user=Mock(),
                    endpoint_name=Mock(return_value='some_machine'),
                    run_script=PropertyMock(return_value=False))
    def test_server_create_new_session_with_user_and_token(self):
        """
        - pass user and token via desired capabilities
        Expected: session created
        """
        _desired_caps = self.desired_caps.copy()
        _desired_caps["desiredCapabilities"]["user"] = "anonymous"
        _desired_caps["desiredCapabilities"]["token"] = None

        response = new_session_request(self.address, _desired_caps)

        from vmpool.virtual_machines_pool import pool
        vm_count = len(pool.using)

        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    def test_server_maximum_vm_running(self):
        """
        - maximum machines in pool
        - try to create new session
        Expected: thread with new session is alive
        """
        from threading import Thread

        from vmpool.virtual_machines_pool import pool
        pool.add('test_origin_1')
        pool.add('test_origin_1')
        with patch('vmmaster.core.sessions.Session.run_script',
                   PropertyMock(return_value=False)):
            t = Thread(target=new_session_request, args=(self.address,
                                                         self.desired_caps))
        t.daemon = True
        t.start()
        self.assertEqual(2, len(pool.using))
        self.assertTrue(t.isAlive())
        t.join(0.1)

    @patch.multiple('vmmaster.core.sessions.Session',
                    set_vm=Mock(),
                    endpoint_name=Mock(return_value='some_machine'))
    def test_delete_session(self):
        """
        - create new session
        - try to get id from response
        - delete session by id
        Expected: session deleted
        """
        from vmmaster.core.sessions import Session
        with patch.object(Session, 'make_request', side_effect=Mock(
                return_value=(200, {}, None))), \
                patch('vmmaster.webdriver.helpers.transparent',
                      Mock(return_value=Response(
                           status=200, headers={}, response=None))):
            session = Session()
            session.id = 1
            session.succeed = Mock()
            session.add_session_step = Mock()

            with patch('vmmaster.core.sessions.Sessions.get_session',
                       Mock(return_value=session)):
                response = delete_session_request(self.address, session.id)
                session.succeed.assert_called_once_with()
            self.assertEqual(200, response.status)

    def test_delete_session_if_got_session_but_session_not_exist(self):
        """
        - create new session
        - try to get id from response
        - delete session by id
        - mocking get_session
        - repeat deleting session
        Expected: session deleted
        """
        from vmmaster.core.sessions import Session
        with patch.object(Session, 'make_request', side_effect=Mock(
                return_value=(200, {}, None))), \
                patch('vmmaster.webdriver.helpers.transparent',
                      Mock(return_value=Response(
                           status=200, headers={}, response=None))):

            session = Session()
            session.id = 1
            session.succeed = Mock()
            session.add_session_step = Mock()

            with patch('vmmaster.core.sessions.Sessions.get_session',
                       Mock(return_value=session)):
                response = delete_session_request(self.address, session.id)
                self.assertEqual(200, response.status)
                response2 = delete_session_request(self.address, session.id)
                self.assertEqual(200, response2.status)

    def test_delete_none_existing_session(self):
        """
        - try to delete session from empty pool
        Expected: exception
        """
        session = uuid4()
        with patch('vmmaster.core.db.database.get_session', Mock(
                return_value=None)):
            response = delete_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" %
                        session in response.content)

    def test_get_none_existing_session(self):
        """
        - try to get session from empty pool
        Expected: exception
        """
        session = uuid4()
        with patch('vmmaster.core.db.database.get_session', Mock(
                return_value=None)):
            response = get_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" %
                        session in response.content)

    @patch('vmmaster.webdriver.helpers.transparent', new=Mock(
        return_value=Response(status=200, headers={}, response=None))
    )
    @patch.multiple('vmmaster.core.sessions.Session',
                    make_request=Mock(
                        side_effect=Mock(return_value=(200, {}, None))),
                    set_vm=Mock(),
                    endpoint_name=Mock(return_value='some_machine'))
    def test_server_deleting_session_on_client_connection_drop(self):
        """
        - create vmmaster session
        - close the connection
        - try to get vmmaster session
        Expected: vmmaster session deleted
        """
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1

        from vmmaster.webdriver.helpers import Request
        with patch.object(Request, 'input_stream',
                          return_result=Mock(_wrapped=Mock(closed=True))),\
                patch('vmmaster.core.sessions.Sessions.get_session',
                      Mock(return_value=session)),\
                patch.object(Session, 'delete') as mock:
            get_session_request(self.address, session.id)

        self.assertTrue(mock.called)

    def test_run_script(self):
        """
        - create vmmaster session
        - send run_script request
        Expected: script executed, output contains echo message
        """
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1
        session.selenium_session = '1'
        output = json.dumps({"output": "hello world\n"})

        from vmmaster.webdriver import commands
        with patch.object(
                commands, 'AgentCommands',
                {'runScript': Mock(return_value=(200, {}, output))}),\
                patch('vmmaster.core.sessions.Sessions.get_session',
                      Mock(return_value=session)):
            response = run_script(
                self.address, session.id, "echo 'hello world'")

        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    def test_vmmaster_label(self):
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1
        output = json.dumps({"value": "step-label"})

        from vmmaster.webdriver import commands
        with patch.object(commands, 'InternalCommands',
                          {'vmmasterLabel':
                           Mock(return_value=(200, {}, output))}),\
            patch('vmmaster.core.sessions.Sessions.get_session',
                  Mock(return_value=session)):
            response = vmmaster_label(self.address, session.id, "step-label")

        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    def test_vmmaster_no_such_platform(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.address, desired_caps)
        error = json.loads(response.content).get('value')

        self.assertIn('PlatformException: No such endpoint for your '
                      'platform no_platform', error)


@patch('vmmaster.core.db.database', new=Mock())
class TestSessionWorker(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')

        from vmmaster.core.sessions import SessionWorker
        self.worker = SessionWorker()

    def tearDown(self):
        self.worker.stop()

    def test_server_timeouted_session(self):
        """
        - create timeouted session
        - run session worker
        Expected: session timeouted
        """

        too_long = config.SESSION_TIMEOUT + 1
        with patch('vmmaster.core.sessions.Session.inactivity',
                   PropertyMock(return_value=too_long)):
            from vmmaster.core.sessions import Session
            session = Session()
            session.id = 1
            session.selenium_session = '1'
            session.timeout = Mock()

            self.worker.active_sessions = Mock(return_value=[session])
            self.worker.start()

            session.timeout.assert_any_call()


class TestSessionStates(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        with patch('vmmaster.core.network.network.Network', Mock()), \
            patch('vmmaster.core.connection.Virsh', Mock()), \
                patch('vmmaster.core.db.database', Mock(
                    get_sessions=Mock(return_value=[])
                )), \
            patch('vmmaster.core.utils.init.home_dir',
                  Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      Mock(return_value=Mock())):

            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmmaster.server import VMMasterServer
            from vmpool.server import VMPool
            from nose.twistedtools import reactor
            self.server = VMMasterServer(reactor, self.address[1])
            self.vmpool = VMPool(reactor, self.vmpool_address[1])

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.vmpool.app.platforms.platforms.keys()[0]
            }
        }

        server_is_up(self.address)
        server_is_up(self.vmpool_address)

        from vmpool.virtual_machines_pool import VirtualMachinesPool
        self.VirtualMachinesPool = VirtualMachinesPool

        # TODO: fix it similar to OpenstackClone mocks
        from vmmaster.core.utils import utils
        utils.delete_file = Mock()
        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()
        KVMClone.id = 1

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()):
            del self.server
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch('vmmaster.core.db.database', new=Mock())
    def test_server_delete_closed_session(self):
        """
        - close existing session
        - try to get closed session
        Expected: session exception
        """
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1
        session.closed = True

        with patch('vmmaster.core.db.database.get_session',
                   new=Mock(return_value=session)):
            response = get_session_request(self.address, session.id)

        self.assertIn("SessionException: There is no active session %s"
                      % session.id, response.content)

    def test_req_closed_during_session_creating(self):
        """
        - close the connection when the session was created
        Expected: session deleted, vm deleted
        """
        def pool_fake_return():
            time.sleep(2)
            return Mock()

        self.assertEqual(0, self.VirtualMachinesPool.count())

        import vmpool.virtual_machines_pool as vmp
        with patch.object(vmp, 'pool', Mock()) as p:
            p.has = Mock(side_effect=pool_fake_return)
            request_with_drop(self.address, self.desired_caps, None)

        self.assertEqual(0, self.VirtualMachinesPool.count())

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

        self.assertEqual(0, self.VirtualMachinesPool.count())


class TestServerShutdown(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        with patch('vmmaster.core.network.network.Network', Mock()), \
            patch('vmmaster.core.connection.Virsh', Mock()), \
                patch('vmmaster.core.db.database', Mock()), \
                patch('vmmaster.core.utils.init.home_dir',
                      Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      Mock(return_value=Mock())), \
                patch('vmmaster.core.sessions.SessionWorker', Mock()):
                from vmmaster.server import VMMasterServer
                from vmpool.server import VMPool
                from nose.twistedtools import reactor
                self.server = VMMasterServer(reactor, self.address[1])
                self.vmpool = VMPool(reactor, self.vmpool_address[1])

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.vmpool.app.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)
        server_is_up(self.vmpool_address)

    def test_server_shutdown(self):
        """
        - shutdown current instance
        Expected: server is down
        """
        with patch('vmmaster.core.db.database', new=Mock()):
            del self.server
            del self.vmpool
            with self.assertRaises(RuntimeError):
                server_is_up(self.address, wait=1)
                server_is_up(self.vmpool_address, wait=1)

    @patch('vmmaster.core.db.database', new=Mock())
    def test_session_is_not_deleted_after_server_shutdown(self):
        """
        - delete server with active session
        Expected: session not deleted
        """
        from vmmaster.core.sessions import Session
        session = Session()
        session.closed = False

        with patch('vmmaster.core.sessions.Sessions.get_session',
                   Mock(return_value=session)):
            del self.server
            del self.vmpool

        self.assertFalse(session.is_closed())
        session.failed()

        server_is_down(self.address)
        server_is_down(self.vmpool_address)


def custom_wait(self, method):
    self.ready = True
    self.checking = False


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="check_vm_online"
))
@patch('vmmaster.webdriver.commands.selenium_status', new=Mock(
    __name__="selenium_status",
    return_value=(200, {}, json.dumps({'status': 0})))
)
@patch('vmmaster.core.db.database', new=Mock())
class TestServerWithPreloadedVM(BaseTestCase):
    def setUp(self):
        setup_config('data/config_with_preloaded.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }
        self.server = None
        self.vmpool = None

        mocked_image = Mock(id=1, status='active',
                            get=Mock(return_value='snapshot'), min_disk=20,
                            min_ram=2, instance_type_flavorid=1)
        type(mocked_image).name = PropertyMock(return_value='test_origin_1')

        with patch('vmmaster.core.network.network.Network', Mock()), \
            patch('vmmaster.core.connection.Virsh', Mock()), \
            patch('vmmaster.core.db.database', Mock()), \
            patch('vmmaster.core.sessions.SessionWorker', Mock()), \
            patch.multiple(
                'vmmaster.core.utils.openstack_utils',
                neutron_client=Mock(return_value=Mock()),
                glance_client=Mock(return_value=Mock()),
                nova_client=Mock(return_value=Mock())), \
            patch.multiple(
                'vmpool.clone.OpenstackClone',
                _wait_for_activated_service=custom_wait,
                get_network_id=Mock(return_value=1),
                get_network_name=Mock(return_value='Local-Net')), \
            patch.multiple(
                'vmpool.platforms.OpenstackPlatforms',
                images=Mock(return_value=[mocked_image]),
                flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
                limits=Mock(return_value={'maxTotalCores': 10,
                                          'maxTotalInstances': 10,
                                          'maxTotalRAMSize': 100,
                                          'totalCoresUsed': 0,
                                          'totalInstancesUsed': 0,
                                          'totalRAMUsed': 0})), \
            patch('vmmaster.core.utils.init.home_dir',
                  Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      Mock(return_value=Mock())):

            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmmaster.server import VMMasterServer
            from vmpool.server import VMPool
            from nose.twistedtools import reactor
            self.server = VMMasterServer(reactor, self.address[1])
            self.vmpool = VMPool(reactor, self.vmpool_address[1])

        server_is_up(self.address)
        server_is_up(self.vmpool_address)

        from vmpool.virtual_machines_pool import VirtualMachinesPool
        self.VirtualMachinesPool = VirtualMachinesPool

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()):
            del self.server
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch('vmpool.clone.OpenstackClone.vm_has_created', new=Mock(
        __name__='vm_has_created',
        return_value=True
    ))
    @patch('vmpool.clone.OpenstackClone.ping_vm', new=Mock(
        __name__='ping_vm',
        return_value=True
    ))
    def test_max_count_with_run_new_request_during_prevm_is_ready(self):
        """
        - wait while preloaded is ready
        - make new session request
        Expected: session created
        """
        while True:
            if self.VirtualMachinesPool.pool[0].ready is True:
                break

        with patch('vmmaster.core.db.models.Session.add_session_step',
                   Mock()),\
                patch.multiple(
                    'vmmaster.core.sessions.Session',
                    set_vm=Mock(),
                    endpoint_name=Mock(return_value='some_machine'),
                    run_script=PropertyMock(return_value=False)):
            response = new_session_request(self.address, self.desired_caps)

        self.assertEqual(200, response.status)
        self.assertEqual(1, self.VirtualMachinesPool.count())

    @patch('vmpool.clone.OpenstackClone.vm_has_created', new=Mock(
        __name__='vm_has_created',
        return_value='False'
    ))
    @patch('vmpool.clone.OpenstackClone.ping_vm', new=Mock(
        __name__='ping_vm',
        return_value='False'
    ))
    def test_max_count_with_run_new_request_during_prevm_is_not_ready(self):
        """
        - do not wait for preloaded vm ready status
        - make new session request
        Expected: session created
        """
        with patch('vmmaster.core.db.models.Session.add_session_step',
                   Mock()),\
                patch.multiple(
                    'vmmaster.core.sessions.Session',
                    set_vm=Mock(),
                    endpoint_name=Mock(return_value='some_machine'),
                    run_script=PropertyMock(return_value=False)):
            response = new_session_request(self.address, self.desired_caps)

        self.assertEqual(200, response.status)
        self.assertEqual(1, self.VirtualMachinesPool.count())

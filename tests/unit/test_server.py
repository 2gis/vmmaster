# coding: utf-8

import json
import time
import unittest
from mock import Mock, patch, PropertyMock
from nose.plugins.attrib import attr

from uuid import uuid4
from vmmaster.core.config import setup_config
from helpers import server_is_up, server_is_down, \
    new_session_request, get_session_request, delete_session_request, \
    vmmaster_label, run_script, request_with_drop, fake_home_dir


def session_id(*args, **kwargs):
    class _Session(object):
        id = uuid4()

    return _Session()


def empty_decorator(f):
    return f


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="check_vm_online", return_value=True)
)
@patch('vmmaster.webdriver.commands.selenium_status', new=Mock(
    __name__="selenium_status",
    return_value=(200, {}, json.dumps({'status': 0})))
)
class TestServer(unittest.TestCase):
    def shortDescription(self):
        return None  # TODO: move to parent

    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'test_origin_1'
            }
        }

        import vmmaster.core.network.network
        import vmmaster.core.connection
        import vmmaster.core.db

        with patch.object(vmmaster.core.network.network, 'Network',
                          new=Mock(name='Network')), \
            patch.object(vmmaster.core.connection, 'Virsh',
                         new=Mock(name='Virsh')), \
            patch.object(vmmaster.core.db, 'database',
                         new=Mock(name='Database', create_session=Mock(
                                  name='create_session_mock',
                                  side_effect=session_id)),
                         ):
            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.VirtualMachinesPool = VirtualMachinesPool

            with patch('vmmaster.core.utils.init.home_dir',
                       new=Mock(return_value=fake_home_dir())), \
                    patch('vmmaster.core.logger.setup_logging',
                          new=Mock(return_value=Mock())):
                from vmmaster.server import VMMasterServer
                from vmpool.server import VMPool
                from nose.twistedtools import reactor
                self.vmmaster = VMMasterServer(reactor, self.address[1])
                self.vmpool = VMPool(reactor, self.vmpool_address[1])

        server_is_up(self.address)
        server_is_up(self.vmpool_address)

        from vmmaster.core.utils import utils
        utils.delete_file = Mock()
        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()
        KVMClone.id = 1

    def tearDown(self):
        with patch('vmmaster.core.db.database',
                   new=Mock(add=Mock(), update=Mock())):
            del self.vmmaster
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_server_create_new_session(self):
        response = new_session_request(self.address, self.desired_caps)
        vm_count = len(self.VirtualMachinesPool.using)
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_server_create_new_session_with_user_and_token(self):
        """
        - pass user and token via desired capabilities
        Expected: session created
        """
        _desired_caps = self.desired_caps.copy()
        _desired_caps["desiredCapabilities"]["user"] = "anonymous"
        _desired_caps["desiredCapabilities"]["token"] = None

        response = new_session_request(self.address, _desired_caps)
        vm_count = len(self.VirtualMachinesPool.using)
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_server_maximum_vm_running(self):
        """
        - maximum machines in pool
        - try to create new session
        Expected: thread with new session is alive
        """
        from threading import Thread
        self.VirtualMachinesPool.using = [Mock()] * 2
        t = Thread(target=new_session_request, args=(self.address,
                                                     self.desired_caps))
        t.daemon = True
        t.start()
        self.assertEqual(2, len(self.VirtualMachinesPool.using))
        self.assertTrue(t.isAlive())
        t.join(0.1)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_delete_session(self):
        """
        - create new session
        - try to get id from response
        - delete session by id
        Expected: session deleted
        """
        from vmmaster.core.sessions import Session
        with patch.object(Session, 'make_request',
                          side_effect=Mock(return_value=(200, {}, None))):
            response = new_session_request(self.address, self.desired_caps)
            _session_id = json.loads(response.content)["sessionId"].encode(
                "utf-8")
            response2 = delete_session_request(self.address, _session_id)
            self.assertEqual(200, response2.status)

    @patch('vmmaster.core.db.database', new=Mock())
    def test_delete_none_existing_session(self):
        """
        - try to delete session from empty pool
        Expected: exception
        """
        session = uuid4()
        response = delete_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" %
                        session in response.content)

    @patch('vmmaster.core.db.database', new=Mock())
    def test_get_none_existing_session(self):
        """
        - try to get session from empty pool
        Expected: exception
        """
        session = uuid4()
        response = get_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" %
                        session in response.content)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock()))
    def test_server_deleting_session_on_client_connection_drop(self):
        """
        - create vmmaster session
        - close the connection
        - try to get vmmaster session
        Expected: vmmaster session deleted
        """
        response = new_session_request(self.address, self.desired_caps)
        _session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        from vmmaster.webdriver.helpers import Request
        with patch.object(Request, 'input_stream',
                          return_result=Mock(_wrapped=Mock(closed=True))):
            from vmmaster.core.sessions import Session
            with patch.object(Session, 'delete') as mock:
                get_session_request(self.address, _session_id)

        self.assertTrue(mock.called)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_run_script(self):
        """
        - create vmmaster session
        - send run_script request
        Expected: script executed, output contains echo message
        """
        response = new_session_request(self.address, self.desired_caps)
        _session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        output = json.dumps({"output": "hello world\n"})

        from vmmaster.webdriver import commands
        with patch.object(commands, 'AgentCommands',
                          {'runScript': Mock(return_value=(200, {}, output))}):
            response = run_script(self.address,
                                  _session_id,
                                  "echo 'hello world'")

        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_vmmaster_label(self):
        response = new_session_request(self.address, self.desired_caps)
        _session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        output = json.dumps({"value": "step-label"})

        from vmmaster.webdriver import commands
        with patch.object(commands, 'InternalCommands',
                          {'vmmasterLabel':
                           Mock(return_value=(200, {}, output))}):
            response = vmmaster_label(self.address, _session_id, "step-label")

        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    @patch('vmmaster.core.db.database', new=Mock(add=Mock()))
    def test_vmmaster_no_such_platform(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.address, desired_caps)
        error = json.loads(response.content).get('value')

        self.assertTrue('PlatformException: No such endpoint for your '
                        'platform no_platform' in error, error)


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="check_vm_online", return_value=True)
)
@patch('vmmaster.webdriver.commands.selenium_status', new=Mock(
    __name__="selenium_status",
    return_value=(200, {}, json.dumps({'status': 0})))
)
class TestTimeoutSession(unittest.TestCase):
    def shortDescription(self):
        return None  # TODO: move to parent

    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        import vmmaster.core.network.network
        import vmmaster.core.connection as connection
        import vmmaster.core.db

        with patch.object(vmmaster.core.network.network, 'Network',
                          new=Mock(name='Network')), \
            patch.object(connection, 'Virsh', new=Mock(name='Virsh')), \
            patch.object(vmmaster.core.db, 'database', new=Mock(
                         name='Database',
                         create_session=Mock(name='create_session_mock',
                                             side_effect=session_id))):

            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.VirtualMachinesPool = VirtualMachinesPool

            with patch('vmmaster.core.utils.init.home_dir',
                       new=Mock(return_value=fake_home_dir())), \
                    patch('vmmaster.core.logger.setup_logging',
                          new=Mock(return_value=Mock())):
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

        from vmmaster.core.utils import utils
        utils.delete_file = Mock()
        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()
        KVMClone.id = 1

    def tearDown(self):
        with patch('vmmaster.core.db.database', new=Mock()):
            del self.server
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch('vmmaster.core.db.database', Mock(add=Mock(), update=Mock()))
    def test_server_delete_timeouted_session(self):
        """
        - create timeouted session
        Expected: session deleted
        """
        response = new_session_request(self.address, self.desired_caps)
        _session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        session = self.server.app.sessions.get_session(_session_id)
        session.timeout()

        vm_count = len(self.VirtualMachinesPool.using)
        self.assertEqual(0, vm_count)

        response = get_session_request(self.address, _session_id)
        self.assertTrue("SessionException: There is no active session %s" %
                        _session_id in response.content,
                        "SessionException: There is no active session %s not "
                        "in %s" % (_session_id, response.content))

    @patch('vmmaster.core.db.database', new=Mock(add=Mock()))
    def test_server_delete_closed_session(self):
        """
        - close existing session
        - try to access closed session
        Expected: session exception
        """
        self.assertEqual(0, self.VirtualMachinesPool.count())
        response = new_session_request(self.address, self.desired_caps)
        _session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        session = self.server.app.sessions.get_session(_session_id)
        session.close()
        vm_count = len(self.VirtualMachinesPool.using)

        self.assertEqual(0, vm_count)
        response = get_session_request(self.address, _session_id)
        self.assertTrue("SessionException: There is no active session %s" %
                        _session_id in response.content,
                        "SessionException: There is no active session %s not "
                        "in %s" % (_session_id, response.content))

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
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
        self.assertEqual(0, len(self.server.app.sessions.map))

    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
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
        vm_count = len(self.VirtualMachinesPool.using)
        self.assertEqual(0, vm_count)
        self.assertEqual(0, len(self.server.app.sessions.map))


class TestServerShutdown(unittest.TestCase):
    def shortDescription(self):
        return None  # TODO: move to parent

    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        import vmmaster.core.network.network as network
        import vmmaster.core.connection as connection
        import vmmaster.core.db as db

        with patch.object(network, 'Network', new=Mock(name='Network')), \
            patch.object(connection, 'Virsh', new=Mock(name='Virsh')), \
            patch.object(db, 'database', new=Mock(name='Database',
                         create_session=Mock(name='create_session_mock',
                                             side_effect=session_id))):

            with patch('vmmaster.core.utils.init.home_dir',
                       new=Mock(return_value=fake_home_dir())), \
                    patch('vmmaster.core.logger.setup_logging',
                          new=Mock(return_value=Mock())):
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

    def test_session_is_not_deleted_after_server_shutdown(self):
        """
        - delete server with active sessions
        Expected: sessions not deleted
        """
        from vmmaster.core.sessions import Session
        s = Session(sessions=self.server.app.sessions,
                    dc=Mock(),
                    vm=None)

        sessions = self.server.app.sessions.map
        sessions[str(s.id)] = s
        self.assertEqual(1, len(sessions))

        del self.server
        del self.vmpool
        self.assertEqual(1, len(sessions))
        s.close()
        server_is_down(self.address)
        server_is_down(self.vmpool_address)


# mocking for Openstack
def custom_wait(self, method):
    self.ready = True

mocked_image = Mock(id=1,
                    status='active',
                    get=Mock(return_value='snapshot'),
                    min_disk=20,
                    min_ram=2,
                    instance_type_flavorid=1)
type(mocked_image).name = PropertyMock(return_value='test_origin_1')


@patch('vmmaster.webdriver.commands.start_selenium_session', new=Mock(
    __name__="start_selenium_session",
    return_value=(200, {}, json.dumps({'sessionId': "1"})))
)
@patch('vmmaster.webdriver.commands.ping_vm', new=Mock(
    __name__="check_vm_online")
)
@patch('vmmaster.webdriver.commands.selenium_status', new=Mock(
    __name__="selenium_status",
    return_value=(200, {}, json.dumps({'status': 0})))
)
class TestServerWithPreloadedVM(unittest.TestCase):
    def shortDescription(self):
        return None  # TODO: move to parent

    def setUp(self):
        setup_config('data/config_with_preloaded.py')
        self.address = ("localhost", 9001)
        self.vmpool_address = ("localhost", 9999)

        from vmpool.clone import OpenstackClone
        from vmmaster.core.utils import openstack_utils

        openstack_utils.nova_client = Mock()
        openstack_utils.neutron_client = Mock()
        openstack_utils.glance_client = Mock()
        openstack_utils.glance_client().images.list = Mock(
            return_value=[mocked_image])
        openstack_utils.nova_client().flavors.find().to_dict = Mock(
            return_value={'vcpus': 1, 'ram': 2})
        openstack_utils.nova_client().limits.get().to_dict = Mock(
            return_value={'absolute': {'maxTotalCores': 10,
                                       'maxTotalInstances': 10,
                                       'maxTotalRAMSize': 100,
                                       'totalCoresUsed': 0,
                                       'totalInstancesUsed': 0,
                                       'totalRAMUsed': 0}})

        OpenstackClone._wait_for_activated_service = custom_wait
        OpenstackClone.get_network_id = Mock(return_value=1)
        OpenstackClone.get_network_name = Mock(return_value='Local-Net')

        import vmmaster.core.network.network as network
        import vmmaster.core.connection as connection
        import vmmaster.core.db

        with patch.object(network, 'Network', new=Mock(name='Network')), \
            patch.object(connection, 'Virsh', new=Mock(name='Virsh')), \
            patch.object(vmmaster.core.db, 'database', new=Mock(
                         name='Database',
                         create_session=Mock(name='create_session_mock',
                                             side_effect=session_id))):

            from vmmaster.core.auth import custom_auth
            custom_auth.user_exists = empty_decorator
            custom_auth.auth.login_required = empty_decorator

            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.VirtualMachinesPool = VirtualMachinesPool

            with patch('vmmaster.core.utils.init.home_dir',
                       new=Mock(return_value=fake_home_dir())), \
                    patch('vmmaster.core.logger.setup_logging',
                          new=Mock(return_value=Mock())):
                from vmmaster.server import VMMasterServer
                from vmpool.server import VMPool
                from nose.twistedtools import reactor
                self.server = VMMasterServer(reactor, self.address[1])
                self.vmpool = VMPool(reactor, self.vmpool_address[1])

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': 'origin_1'
            }
        }
        server_is_up(self.address)
        server_is_up(self.vmpool_address)

    def tearDown(self):
        with patch('vmmaster.core.db.database',
                   new=Mock(add=Mock(), update=Mock())):
            del self.server
            del self.vmpool
            server_is_down(self.address)
            server_is_down(self.vmpool_address)

    @patch('vmpool.clone.OpenstackClone.vm_has_created',
           new=Mock(__name__='vm_has_created', return_value='True'))
    @patch('vmpool.clone.OpenstackClone.ping_vm',
           new=Mock(__name__='ping_vm', return_value='True'))
    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_max_count_with_run_new_request_during_prevm_is_ready(self):
        """
        - wait while preloaded is ready
        - make new session request
        Expected: session created
        """
        while True:
            if self.VirtualMachinesPool.pool[0].ready is True:
                break
        response = new_session_request(self.address, self.desired_caps)
        vm_count = len(self.VirtualMachinesPool.pool +
                       self.VirtualMachinesPool.using)
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    @patch('vmpool.clone.OpenstackClone.vm_has_created',
           new=Mock(__name__='vm_has_created', return_value='False'))
    @patch('vmpool.clone.OpenstackClone.ping_vm',
           new=Mock(__name__='ping_vm', return_value='False'))
    @patch('vmmaster.core.db.database', new=Mock(add=Mock(), update=Mock()))
    def test_max_count_with_run_new_request_during_prevm_is_not_ready(self):
        """
        - do not wait for preloaded vm ready status
        - make new session request
        Expected: session created
        """
        response = new_session_request(self.address, self.desired_caps)
        vm_count = self.VirtualMachinesPool.count()
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

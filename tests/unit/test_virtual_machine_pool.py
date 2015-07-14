# coding: utf-8

from mock import Mock, patch
from vmmaster.core.exceptions import CreationException
from vmmaster.core.config import config, setup_config
from vmpool import VirtualMachine
from vmpool.virtual_machines_pool import pool
from vmmaster.core.utils import utils
from helpers import BaseTestCase
utils.delete_file = Mock()


@patch('vmmaster.core.db.database', Mock(add=Mock(), update=Mock()))
class TestVirtualMachinePool(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')

        import vmmaster.core.connection as connection
        import vmmaster.core.network.network as network

        with patch.object(connection, 'Virsh', Mock(name='Virsh')), \
                patch.object(network, 'Network', Mock(name='Network')):
            from vmpool.platforms import Platforms
            from vmmaster.core.network.network import Network
            Platforms()
            self.network = Network()

        self.platform = "test_origin_1"

        from vmpool.clone import Clone
        Clone.ping_vm = Mock(__name__="ping_vm")

        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()

    @patch('vmmaster.core.db.database', Mock(add=Mock(), update=Mock()))
    def tearDown(self):
        pool.free()

    def test_pool_count(self):
        self.assertEqual(0, pool.count())
        pool.add(self.platform)
        self.assertEqual(1, pool.count())

    def test_get_parallel_two_vm(self):
        from multiprocessing.pool import ThreadPool
        threads = ThreadPool(processes=1)
        pool.preload(self.platform)
        pool.preload(self.platform)

        self.assertEqual(2, len(pool.pool))

        deffered1 = threads.apply_async(pool.get, args=(self.platform,))
        deffered2 = threads.apply_async(pool.get, args=(self.platform,))
        deffered1.wait()
        deffered2.wait()

        self.assertEqual(2, len(pool.using))

    def test_vm_preloading(self):
        self.assertEqual(0, len(pool.pool))
        pool.preload(self.platform)
        self.assertIsInstance(pool.pool[0], VirtualMachine)
        self.assertEqual(1, len(pool.pool))

    def test_vm_adding(self):
        self.assertEqual(0, len(pool.pool))
        pool.add(self.platform)
        self.assertIsInstance(pool.using[0], VirtualMachine)
        self.assertEqual(1, len(pool.using))

    def test_vm_deletion(self):
        self.assertEqual(0, len(pool.pool))
        pool.preload(self.platform)
        self.assertEqual(1, len(pool.pool))
        vm = pool.get(self.platform)
        vm.delete()
        self.assertEqual(0, pool.count())

    def test_max_vm_count(self):
        config.KVM_MAX_VM_COUNT = 2

        pool.add(self.platform)
        pool.add(self.platform)

        with self.assertRaises(CreationException) as e:
            pool.add(self.platform)

        the_exception = e.exception
        self.assertEqual("maximum count of virtual machines already running",
                         the_exception.message)

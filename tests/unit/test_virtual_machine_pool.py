# coding: utf-8

from mock import Mock, patch
from core.config import config, setup_config
from helpers import BaseTestCase


@patch('core.db.database', Mock())
class TestVirtualMachinePool(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.platform = "test_origin_1"

        with patch('core.connection.Virsh', Mock()), \
                patch('core.network.Network', Mock()):
            from vmpool.platforms import Platforms
            from core.network import Network
            Platforms()
            self.network = Network()

            from vmpool.virtual_machines_pool import pool
            self.pool = pool

        # TODO: mock it like openstack clone in test_server
        from vmpool.clone import Clone
        Clone.ping_vm = Mock(__name__="ping_vm")

        from vmpool.clone import KVMClone
        KVMClone.clone_origin = Mock()
        KVMClone.define_clone = Mock()
        KVMClone.start_virtual_machine = Mock()
        KVMClone.drive_path = Mock()

    def tearDown(self):
        with patch('core.db.database', Mock()), \
                patch('core.utils.delete_file', Mock()):
            self.pool.free()

    def test_pool_count(self):
        self.assertEqual(0, self.pool.count())
        self.pool.add(self.platform)
        self.assertEqual(1, self.pool.count())

    def test_get_parallel_two_vm(self):
        from multiprocessing.pool import ThreadPool
        threads = ThreadPool(processes=1)
        self.pool.preload(self.platform)
        self.pool.preload(self.platform)

        self.assertEqual(2, len(self.pool.pool))

        deffered1 = threads.apply_async(
            self.pool.get_by_platform, args=(self.platform,))
        deffered2 = threads.apply_async(
            self.pool.get_by_platform, args=(self.platform,))
        deffered1.wait()
        deffered2.wait()

        self.assertEqual(2, len(self.pool.using))

    def test_vm_preloading(self):
        self.assertEqual(0, len(self.pool.pool))
        self.pool.preload(self.platform)

        from vmpool import VirtualMachine
        self.assertIsInstance(self.pool.pool[0], VirtualMachine)
        self.assertEqual(1, len(self.pool.pool))

    def test_vm_adding(self):
        self.assertEqual(0, len(self.pool.pool))
        self.pool.add(self.platform)

        from vmpool import VirtualMachine
        self.assertIsInstance(self.pool.using[0], VirtualMachine)
        self.assertEqual(1, len(self.pool.using))

    def test_vm_deletion(self):
        self.assertEqual(0, len(self.pool.pool))
        self.pool.preload(self.platform)
        self.assertEqual(1, len(self.pool.pool))

        vm = self.pool.get_by_platform(self.platform)
        with patch('core.utils.delete_file', Mock()):
            vm.delete()

        self.assertEqual(0, self.pool.count())

    def test_max_vm_count(self):
        config.KVM_MAX_VM_COUNT = 2

        self.pool.add(self.platform)
        self.pool.add(self.platform)

        self.assertIsNone(self.pool.add(self.platform))

    def test_platform_from_config(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': "test_origin_1"
            }
        }

        config.PLATFORM = "test_origin_2"

        from vmpool.endpoint import get_vm
        for vm in get_vm(desired_caps):
            self.assertEqual(vm.platform, config.PLATFORM)
            break

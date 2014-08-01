import unittest

from vmmaster.core.platform import Platforms
from vmmaster.core.config import config, setup_config
from vmmaster.core.virtual_machine.virtual_machine import VirtualMachine
from vmmaster.core.exceptions import PlatformException
from vmmaster.core.network.network import Network


class TestPlatforms(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.platforms = Platforms()
        self.platform = "test_origin_1"
        self.network = Network()

    def tearDown(self):
        self.platforms.delete()

    def test_platforms_count(self):
        self.assertEqual(2, len(self.platforms.platforms))

    def test_create_parallel_two_platforms(self):
        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=1)
        deffered1 = pool.apply_async(self.platforms.create, (self.platform, 1))
        deffered2 = pool.apply_async(self.platforms.create, (self.platform, 2))
        deffered1.wait()
        deffered2.wait()

        self.assertEqual(2, self.platforms.vm_count)

    def test_vm_creation(self):
        self.assertEqual(0, self.platforms.vm_count)
        vm = self.platforms.create(self.platform, 1)
        self.assertIsInstance(vm, VirtualMachine)
        self.assertEqual(1, self.platforms.vm_count)

    def test_vm_deletion(self):
        vm = self.platforms.create(self.platform, 1)
        self.assertEqual(1, self.platforms.vm_count)
        vm.delete()
        self.assertEqual(0, self.platforms.vm_count)

    def test_max_vm_count(self):
        config.MAX_VM_COUNT = 2

        self.platforms.create(self.platform, 1)
        self.platforms.create(self.platform, 2)
        with self.assertRaises(PlatformException) as e:
            self.platforms.create(self.platform, 3)

        the_exception = e.exception
        self.assertEqual("maximum count of virtual machines already running", the_exception.message)
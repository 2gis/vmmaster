# coding: utf-8

from mock import Mock, patch, PropertyMock
from core.config import config, setup_config
from helpers import BaseTestCase, custom_wait
from flask import Flask


@patch('core.utils.openstack_utils.nova_client', Mock())
@patch.multiple(
    'vmpool.clone.OpenstackClone',
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True)
)
class TestVirtualMachinePool(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.platform = "origin_1"

        self.app = Flask(__name__)

        self.ctx = self.app.app_context()
        self.ctx.push()

        self.mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1,
        )
        type(self.mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
        ):
            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.pool = VirtualMachinesPool(self.app)

            from vmmaster.matcher import SeleniumMatcher, PoolBasedMatcher
            self.app.matcher = SeleniumMatcher(config.PLATFORMS, PoolBasedMatcher(self.pool))

    def tearDown(self):
        self.pool.free()
        self.ctx.pop()

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
        vm.delete()

        self.assertEqual(0, self.pool.count())

    def test_max_vm_count(self):
        config.OPENSTACK_MAX_VM_COUNT = 2

        self.pool.add(self.platform)
        self.pool.add(self.platform)

        self.assertIsNone(self.pool.add(self.platform))

    def test_platform_from_config(self):
        desired_caps = {
            'platform': "origin_2"
        }

        config.PLATFORM = "origin_1"
        self.app.pool = self.pool

        from vmpool.endpoint import get_vm
        for vm in get_vm(desired_caps):
            self.assertEqual(vm.platform, config.PLATFORM)
            break

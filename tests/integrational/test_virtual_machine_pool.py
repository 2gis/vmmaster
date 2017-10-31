# coding: utf-8

from mock import Mock, patch, PropertyMock
from core.config import setup_config, config
from tests.helpers import BaseTestCase, custom_wait
from flask import Flask


@patch('core.utils.openstack_utils.nova_client', Mock())
@patch.multiple(
    'core.db.models.OpenstackClone',
    _wait_for_activated_service=custom_wait,
    ping_vm=Mock(return_value=True),
    ready=PropertyMock(return_value=True)
)
class TestVirtualMachinePool(BaseTestCase):
    def setUp(self):
        from core.db import Database
        setup_config('data/config.py')
        self.platform_name = "origin_1"
        self.app = Flask(__name__)

        self.ctx = self.app.app_context()
        self.ctx.push()
        self.app.database = Database()
        self.app.sessions = Mock()

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
            self.pool = VirtualMachinesPool(
                self.app, preloader_class=Mock(), artifact_collector_class=Mock(), endpoint_preparer_class=Mock()
            )
            self.ctx = self.app.app_context()
            self.ctx.push()
            self.pool.register()

    def tearDown(self):
        self.pool.endpoint_remover.remove_all()
        self.pool.unregister()
        self.pool.platforms.cleanup()
        self.ctx.pop()

    def test_run_workers(self):
        self.pool.endpoint_remover.start = Mock()
        self.pool.start_workers()

        self.assertTrue(self.pool.endpoint_preparer.start.called)
        self.assertTrue(self.pool.endpoint_remover.start.called)
        self.assertTrue(self.pool.preloader.start.called)

    def test_stop_workers(self):
        self.pool.endpoint_remover.stop = Mock()
        self.pool.stop_workers()

        self.assertTrue(self.pool.endpoint_preparer.stop.called)
        self.assertTrue(self.pool.endpoint_remover.stop.called)
        self.assertTrue(self.pool.artifact_collector.stop.called)
        self.assertTrue(self.pool.preloader.stop.called)

    def test_pool_count(self):
        self.assertEqual(0, len(self.pool.active_endpoints))
        self.pool.add(self.platform_name)
        self.assertEqual(1, len(self.pool.active_endpoints))

    def test_get_parallel_two_vm(self):
        from multiprocessing.pool import ThreadPool
        threads = ThreadPool(processes=1)
        self.pool.preload(self.platform_name)
        self.pool.preload(self.platform_name)

        self.assertEqual(2, len(self.pool.active_endpoints))

        deffered1 = threads.apply_async(
            self.pool.get_by_platform, args=(self.platform_name,))
        deffered2 = threads.apply_async(
            self.pool.get_by_platform, args=(self.platform_name,))
        deffered1.wait()
        deffered2.wait()

        self.assertEqual(2, len(self.pool.active_endpoints))

    def test_vm_preloading(self):
        self.assertEqual(0, len(self.pool.active_endpoints))
        self.pool.preload(self.platform_name)

        from core.db.models import OpenstackClone
        self.assertIsInstance(self.pool.active_endpoints[0], OpenstackClone)
        self.assertEqual(1, len(self.pool.active_endpoints))

    def test_vm_adding(self):
        self.assertEqual(0, len(self.pool.active_endpoints))
        self.pool.add(self.platform_name)

        from core.db.models import OpenstackClone
        self.assertIsInstance(self.pool.active_endpoints[0], OpenstackClone)
        self.assertEqual(1, len(self.pool.active_endpoints))

    def test_vm_deletion(self):
        self.assertEqual(0, len(self.pool.active_endpoints))
        clone = self.pool.preload(self.platform_name)
        self.assertEqual(1, len(self.pool.active_endpoints))

        clone.delete()
        self.app.database.delete(clone)

        self.assertEqual(0, len(self.pool.active_endpoints))

    def test_max_vm_count(self):
        config.OPENSTACK_MAX_VM_COUNT = 2

        self.pool.add(self.platform_name)
        self.pool.add(self.platform_name)

        self.assertIsNone(self.pool.add(self.platform_name))

# coding: utf-8

from mock import Mock, patch, PropertyMock
from core.config import setup_config
from tests.unit.helpers import wait_for, BaseTestCase


def custom_wait(self, method):
    self.ready = True
    self.checking = False


@patch(
    'vmpool.virtual_machines_pool.VirtualMachinesPool.can_produce',
    new=Mock(return_value=True)
)
@patch.multiple(
    'core.utils.openstack_utils',
    nova_client=Mock(return_value=Mock())
)
class TestOpenstackClone(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')

        self.platform = "origin_1"
        self.address = ("localhost", 9001)

        self.mocked_image = Mock(
            id=1, status='active',
            get=Mock(return_value='snapshot'),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1
        )
        type(self.mocked_image).name = PropertyMock(
            return_value='test_origin_1')

        with patch(
            'core.connection.Virsh', Mock(),
        ), patch(
            'core.network.Network', Mock()
        ), patch.multiple(
            'core.utils.openstack_utils',
            nova_client=Mock(return_value=Mock())
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0})
        ):
            from flask import Flask
            self.app = Flask(__name__)

            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.app.pool = VirtualMachinesPool(self.app)

            from vmpool.platforms import Platforms
            self.app.platforms = Platforms()

            self.ctx = self.app.test_request_context()
            self.ctx.push()

    def tearDown(self):
        self.app.platforms.cleanup()
        self.app.pool.free()
        del self.app.pool
        self.ctx.pop()

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        _wait_for_activated_service=custom_wait
    )
    def test_creation_vm(self):
        """
        - call OpenstackClone.create()
        - _wait_for_activated_service has been mocked

        Expected: vm has been created
        """
        self.app.pool.add(self.platform)
        self.assertTrue(self.app.pool.using[0].ready)
        self.assertEqual(len(self.app.pool.using), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(return_value=None)
    )
    def test_exception_during_creation_vm(self):
        """
        - call OpenstackClone.create()
        - get_vm() return None

        Expected: vm has been deleted
        """
        self.app.pool.add(self.platform)
        wait_for(lambda: self.app.pool.count() == 0)
        self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(return_value=None)
    )
    def test_exception_in_wait_for_activated_service_and_rebuild_failed(self):
        """
        - call OpenstackClone.create()
        - get_vm() is None
        - call delete()

        Expected: vm has been deleted
        """
        self.app.pool.add(self.platform)
        wait_for(lambda: self.app.pool.count() == 0)
        self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_ip=Mock(),
        get_vm=Mock(return_value=Mock(status="active"))
    )
    @patch.multiple(
        'core.utils.network_utils',
        ping=Mock(return_value=True)
    )
    def test_ping_success(self):
        """
        - call OpenstackClone.create()
        - ping success

        Expected: vm has been created
        """
        self.app.pool.add(self.platform)

        wait_for(lambda: self.app.pool.using[0].ready is True)
        self.assertEqual(self.app.pool.count(), 1)
        self.assertTrue(self.app.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_ip=Mock(),
        get_vm=Mock(return_value=Mock(status="active")),
        ping_vm=Mock(return_value=True)
    )
    def test_exception_in_wait_for_activated_service_and_ping_success(self):
        """
        - call OpenstackClone.create()
        - get_vm() return Mock and is_active is True
        - ping success

        Expected: vm has been created
        """
        self.app.pool.add(self.platform)

        wait_for(lambda: self.app.pool.using[0].ready is True)
        self.assertEqual(self.app.pool.count(), 1)
        self.assertTrue(self.app.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_ip=Mock(),
        get_vm=Mock(return_value=Mock(status='active')),
        rebuild=Mock(return_value=True),
        ping_vm=Mock(side_effect=[False, True])
    )
    def test_exception_in_wait_for_activated_service_and_ping_failed(self):
        """
        - call OpenstackClone.create()
        - is_active is True
        - ping failed

        Expected: vm has been rebuilded
        """
        self.app.pool.add(self.platform)
        self.assertEqual(self.app.pool.count(), 1)

    @patch('vmpool.clone.OpenstackClone._wait_for_activated_service', custom_wait)
    def test_exception_in_getting_image(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.image

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(create=Mock(),
                                                  status="active"),
                                     glance=Mock(
                                         find_image=Mock(side_effect=Exception(
                                             'Exception in image'))))

            self.app.pool.add(self.platform)
            self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        image=Mock(),
        _wait_for_activated_service=custom_wait
    )
    def test_exception_in_getting_flavor(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.flavor

        Expected: vm has been deleted
        """
        with patch(
            'core.utils.openstack_utils.nova_client'
        ) as nova:
            nova.return_value = Mock(
                servers=Mock(create=Mock(),
                             status="active"),
                flavors=Mock(find=Mock(
                    side_effect=Exception('Exception in flavor')))
            )

            self.app.pool.add(self.platform)
            self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        _wait_for_activated_service=custom_wait,
        get_vm=Mock(status="active", delete=Mock(), rebuild=Mock())
    )
    def test_delete_vm(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        self.app.pool.add(self.platform)
        self.app.pool.using[0].delete()
        self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(side_effect=[
            Mock(status="active", delete=Mock(), rebuild=Mock()),
            None
        ]),
        _wait_for_activated_service=custom_wait
    )
    def test_delete_vm_if_vm_does_not_exist(self):
        """
        - call OpenstackClone.create()
        - get_vm return None
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        self.app.pool.add(self.platform)
        self.app.pool.using[0].delete()
        self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        _wait_for_activated_service=custom_wait,
        get_vm=Mock(status="active", delete=Mock(), rebuild=Mock())
    )
    def test_rebuild_preload_vm(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        self.app.pool.preload(self.platform, prefix='preloaded')
        wait_for(lambda: self.app.pool.pool[0].ready is True)
        self.app.pool.pool[0].rebuild()
        wait_for(lambda: self.app.pool.pool[0].ready is True)
        self.assertEqual(self.app.pool.count(), 1)
        self.assertTrue(self.app.pool.pool[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_ip=Mock(__name__='get_ip'),
        get_vm=Mock(return_value=Mock(delete=Mock(), rebuild=Mock(), status='active')),
        ping_vm=Mock(return_value=True)
    )
    def test_rebuild_ondemand_vm_with_wait_activate_service(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        self.app.pool.add(self.platform, prefix='ondemand')
        wait_for(lambda: self.app.pool.using[0].ready is True)
        self.app.pool.using[0].rebuild()
        wait_for(lambda: self.app.pool.using[0].ready is True)
        self.assertEqual(self.app.pool.count(), 1)
        self.assertTrue(self.app.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(return_value=Mock(delete=Mock(), rebuild=Mock(), status='active')),
        ping_vm=Mock(return_value=True)
    )
    def test_rebuild_preload_vm_with_wait_activate_service(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        self.app.pool.preload(self.platform, prefix='preloaded')
        wait_for(lambda: self.app.pool.pool[0].ready is True)
        self.app.pool.pool[0].rebuild()
        wait_for(lambda: self.app.pool.pool[0].ready is True)
        self.assertEqual(self.app.pool.count(), 1)
        self.assertTrue(self.app.pool.pool[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(side_effect=[
            Mock(delete=Mock(), rebuild=Mock(side_effect=Exception('Rebuild error')), status='active'),
            None
        ]),
        _wait_for_activated_service=custom_wait
    )
    def test_rebuild_vm_if_vm_does_not_exist(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            self.app.pool.add(self.platform)
            wait_for(lambda: self.app.pool.using[0].ready is True)
            self.app.pool.using[0].rebuild()
            self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(return_value=Mock(
            delete=Mock(), rebuild=Mock(side_effect=Exception('Rebuild error')), status='active')
        ),
        _wait_for_activated_service=custom_wait
    )
    def test_exception_in_rebuild_vm_if_vm_exist(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(status="active", delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            self.app.pool.add(self.platform)
            wait_for(lambda: self.app.pool.using[0].ready is True)
            self.app.pool.using[0].rebuild()
            self.assertEqual(self.app.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        ping_vm=Mock(return_value=True),
        get_vm=Mock(return_value=Mock(
            rebuild=Mock(return_value=True),
            status=Mock(lower=Mock(side_effect=['build', 'error', 'active'])))
        ),
        get_ip=Mock(__name__='get_ip')
    )
    def test_vm_in_error_status(self):
        """
        - call OpenstackClone.create()
        - first call server.status.lower() return 'build',
          second call return 'error'
          third call return 'active'
        Expected: vm has been created
        """
        self.app.pool.add(self.platform)
        self.assertEqual(self.app.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        get_vm=Mock(return_value=Mock(
            status='active',
            addresses=Mock(get=Mock(side_effect=Exception('Error get addresses'))),
            rebuild=Mock(side_effect=Exception('Rebuild exception'))
        ),
        )
    )
    def test_exception_in_get_ip(self, ):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - exception in Openstack.get_ip()
        - exception in OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova,\
                patch('vmpool.clone.OpenstackClone.ping_vm') as ping_mock:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(addresses=Mock(
                    get=Mock(side_effect=Exception('Error get addresses'))),
                    rebuild=Mock(side_effect=Exception('Rebuild exception')))))
            )
            ping_mock.side_effect = False
            self.app.pool.add(self.platform)
            wait_for(lambda: self.app.pool.count() > 0)
            self.assertEqual(self.app.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        ping_vm=Mock(return_value=True),
        is_created=Mock(return_value=True),
        get_vm=Mock(
            return_value=Mock(
                status="active",
                networks=Mock(get=Mock(
                    return_value=['127.0.0.1']),
                    status=Mock(lower=Mock(return_value='active')),
                ))
        )
    )
    def test_create_vm_with_get_ip(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - is_created is True
        - get_ip return mocked ip address and mac

        Expected: vm has been created
        """
        self.app.pool.add(self.platform)
        wait_for(lambda: self.app.pool.using[0].ready is True)
        self.assertEqual(self.app.pool.using[0].ip, '127.0.0.1')
        self.assertEqual(self.app.pool.count(), 1)


@patch.multiple(
    'core.utils.openstack_utils',
    nova_client=Mock(return_value=Mock())
)
@patch.multiple(
    'vmpool.clone.OpenstackClone',
    ping_vm=Mock(return_value=True),
    get_vm=Mock(return_value=Mock(rebuild=Mock(), status="active")),
    get_ip=Mock(__name__='get_ip')
)
@patch(
    'vmpool.virtual_machines_pool.VirtualMachinesPool.can_produce',
    new=Mock(return_value=True)
)
class TestNetworkGetting(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.platform = "origin_1"

        mocked_image = Mock(
            id=1, status='active', get=Mock(
                return_value='snapshot'),
            min_disk=20, min_ram=2, instance_type_flavorid=1)
        type(mocked_image).name = PropertyMock(return_value='test_origin_1')

        with patch(
            'core.network.Network', Mock()
        ), patch(
            'core.connection.Virsh', Mock()
        ), patch.multiple(
            'core.utils.openstack_utils',
            nova_client=Mock(),
        ), patch(
            'vmpool.platforms.OpenstackPlatforms.images',
            Mock(return_value=[mocked_image])
        ):
            from flask import Flask
            self.app = Flask(__name__)

            from vmpool.virtual_machines_pool import VirtualMachinesPool
            self.app.pool = VirtualMachinesPool(self.app)

            self.ctx = self.app.test_request_context()
            self.ctx.push()

    def tearDown(self):
        self.app.pool.platforms.cleanup()
        self.app.pool.free()
        del self.app.pool
        self.ctx.pop()

    def test_create_vm_with_getting_network_id_and_name(self):
        """
        - call OpenstackClone.create()
        - ping successful
        - is_created is True
        - call get_network_name

        Expected: vm has been created
        """
        self.app.pool.add(self.platform)
        self.assertEqual(self.app.pool.count(), 1)

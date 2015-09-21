# coding: utf-8

from mock import Mock, patch, PropertyMock
from core.config import setup_config
from tests.unit.helpers import wait_for, BaseTestCase
from core.exceptions import CreationException


def custom_wait(self, method):
    self.ready = True
    self.checking = False


@patch(
    'vmpool.virtual_machines_pool.VirtualMachinesPool.can_produce',
    new=Mock(return_value=True)
)
@patch.multiple(
    'vmpool.clone.OpenstackClone',
    get_network_name=Mock(return_value='Local-Net'),
    get_network_id=Mock(return_value=1)
)
@patch.multiple(
    'core.utils.openstack_utils',
    neutron_client=Mock(return_value=Mock()),
    nova_client=Mock(return_value=Mock()),
    glance_client=Mock(return_value=Mock())
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
            neutron_client=Mock(return_value=Mock()),
            nova_client=Mock(return_value=Mock()),
            glance_client=Mock(return_value=Mock())
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0})
        ):
            from vmpool.virtual_machines_pool import pool
            self.pool = pool

            from vmpool.platforms import Platforms
            self.platforms = Platforms()

    def tearDown(self):
        self.pool.free()
        del self.pool
        self.platforms.cleanup()

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
        self.pool.add(self.platform)
        self.assertTrue(self.pool.using[0].ready)
        self.assertEqual(len(self.pool.using), 1)

    def test_exception_during_creation_vm(self):
        """
        - call OpenstackClone.create()
        - exception in create()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(
                servers=Mock(create=Mock(
                    side_effect=Exception('Exception in create'))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=False),
        check_vm_exist=Mock(return_value=True),
        rebuild=Mock(return_value=True)
    )
    def test_e_in_wait_for_activated_service_and_vm_has_not_been_created(self):
        """
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is False

        Expected: vm has been rebuilded
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=False),
        check_vm_exist=Mock(return_value=True)
    )
    def test_exception_in_wait_for_activated_service_and_rebuild_failed(self):
        """
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is False
        - call rebuild() and raise Exception in rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))

            self.pool.add(self.platform)
            wait_for(lambda: self.pool.count() == 0)
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=True),
        get_ip=Mock(),
        ping_vm=Mock(return_value=True)
    )
    def test_exception_in_wait_for_activated_service_and_ping_success(self):
        """
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is True
        - ping success

        Expected: vm has been created
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(
                servers=Mock(
                    find=Mock(side_effect=Exception(
                        'Exception in _wait_for_activated_service'))))
            self.pool.add(self.platform)

            wait_for(lambda: self.pool.using[0].ready is True)
            self.assertEqual(self.pool.count(), 1)
            self.assertTrue(self.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=True),
        get_ip=Mock(),
        rebuild=Mock(return_value=True),
        ping_vm=Mock(return_value=False)
    )
    def test_exception_in_wait_for_activated_service_and_ping_failed(self):
        """
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is True
        - ping failed

        Expected: vm has been rebuilded
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 1)

    def test_exception_in_getting_image(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.image

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(create=Mock()),
                                     images=Mock(
                                         find=Mock(side_effect=Exception(
                                             'Exception in image'))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 0)

    @patch('vmpool.clone.OpenstackClone.image', Mock())
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
                servers=Mock(create=Mock()),
                flavors=Mock(find=Mock(
                    side_effect=Exception('Exception in flavor')))
            )

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        _wait_for_activated_service=custom_wait
    )
    def test_delete_vm(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.add(self.platform)
            self.pool.using[0].delete()
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=False),
        _wait_for_activated_service=custom_wait
    )
    def test_delete_vm_if_vm_does_not_exist(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is False
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.add(self.platform)
            self.pool.using[0].delete()
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        _wait_for_activated_service=custom_wait
    )
    def test_rebuild_preload_vm(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.preload(self.platform, prefix='preloaded')
            wait_for(lambda: self.pool.pool[0].ready is True)
            self.pool.pool[0].rebuild()
            wait_for(lambda: self.pool.pool[0].ready is True)
            self.assertEqual(self.pool.count(), 1)
            self.assertTrue(self.pool.pool[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        _wait_for_activated_service=custom_wait
    )
    def test_rebuild_ondemand_vm(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.add(self.platform, prefix='ondemand')
            wait_for(lambda: self.pool.using[0].ready is True)
            self.pool.using[0].rebuild()
            wait_for(lambda: self.pool.using[0].ready is True)
            self.assertEqual(self.pool.count(), 1)
            self.assertTrue(self.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=True),
        get_ip=Mock(__name__='get_ip'),
        ping_vm=Mock(return_value=True)
    )
    def test_rebuild_ondemand_vm_with_wait_activate_service(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.add(self.platform, prefix='ondemand')
            wait_for(lambda: self.pool.using[0].ready is True)
            self.pool.using[0].rebuild()
            wait_for(lambda: self.pool.using[0].ready is True)
            self.assertEqual(self.pool.count(), 1)
            self.assertTrue(self.pool.using[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        vm_has_created=Mock(return_value=True),
        get_ip=Mock(__name__='get_ip'),
        ping_vm=Mock(return_value=True)
    )
    def test_rebuild_preload_vm_with_wait_activate_service(self):
        """
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            self.pool.preload(self.platform, prefix='preloaded')
            wait_for(lambda: self.pool.pool[0].ready is True)
            self.pool.pool[0].rebuild()
            wait_for(lambda: self.pool.pool[0].ready is True)
            self.assertEqual(self.pool.count(), 1)
            self.assertTrue(self.pool.pool[0].ready)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=False),
        _wait_for_activated_service=custom_wait
    )
    def test_rebuild_vm_if_vm_does_not_exist(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is False
        - call OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            self.pool.add(self.platform)
            wait_for(lambda: self.pool.using[0].ready is True)
            self.pool.using[0].rebuild()
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        _wait_for_activated_service=custom_wait
    )
    def test_exception_in_rebuild_vm_if_vm_exist(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - exception in OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            self.pool.add(self.platform)
            wait_for(lambda: self.pool.using[0].ready is True)
            self.pool.using[0].rebuild()
            self.assertEqual(self.pool.count(), 0)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        ping_vm=Mock(return_value=True),
        rebuild=Mock(return_value=True),
        get_ip=Mock(__name__='get_ip')
    )
    def test_exception_in_vm_has_created(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - exception in vm_has_created()

        Expected: vm has been rebuilded
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(
                servers=Mock(find=Mock(side_effect=Exception(
                    'Exception in vm_has_created'))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        ping_vm=Mock(return_value=True),
        vm_has_created=Mock(return_value=True),
        get_ip=Mock(__name__='get_ip')
    )
    def test_vm_in_build_status(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - first call server.status.lower() return 'build',
          second call return 'active'
        Expected: vm has been created
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(status=Mock(lower=Mock(
                    side_effect=['build', 'active']))))))
            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        vm_has_created=Mock(return_value=True)
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
                patch('vmpool.clone.'
                      'OpenstackClone.ping_vm') as ping_mock:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(addresses=Mock(
                    get=Mock(side_effect=Exception('Error get addresses'))),
                    rebuild=Mock(side_effect=Exception('Rebuild exception')))))
            )
            ping_mock.side_effect = False
            self.pool.add(self.platform)
            wait_for(lambda: self.pool.count() > 0)
            self.assertEqual(self.pool.count(), 1)

    @patch.multiple(
        'vmpool.clone.OpenstackClone',
        check_vm_exist=Mock(return_value=True),
        ping_vm=Mock(return_value=True),
        vm_has_created=Mock(return_value=True)
    )
    def test_create_vm_with_get_ip(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - get_ip return mocked ip address and mac

        Expected: vm has been created
        """
        with patch('core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(addresses=Mock(get=Mock(
                    return_value=[{'addr': '127.0.0.1',
                                   'OS-EXT-IPS-MAC:mac_addr': 'test_mac'}])))))
            )
            self.pool.add(self.platform)
            wait_for(lambda: self.pool.using[0].ready is True)
            self.assertEqual(self.pool.using[0].ip, '127.0.0.1')
            self.assertEqual(self.pool.using[0].mac, 'test_mac')
            self.assertEqual(self.pool.count(), 1)


@patch.multiple(
    'core.utils.openstack_utils',
    neutron_client=Mock(return_value=Mock()),
    nova_client=Mock(return_value=Mock()),
    glance_client=Mock(return_value=Mock())
)
@patch.multiple(
    'vmpool.clone.OpenstackClone',
    check_vm_exist=Mock(return_value=False),
    ping_vm=Mock(return_value=True),
    vm_has_created=Mock(return_value=True),
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
            nova_client=Mock(return_value=Mock()),
            neutron_client=Mock(return_value=Mock()),
            glance_client=Mock(return_value=Mock())
        ), patch(
            'vmpool.platforms.OpenstackPlatforms.images',
            Mock(return_value=[mocked_image])
        ):
            from vmpool.platforms import Platforms
            self.platforms = Platforms()

            from vmpool.virtual_machines_pool import pool
            self.pool = pool

    def tearDown(self):
        with patch('core.db.database', new=Mock()):
            self.pool.free()
        self.platforms.cleanup()

    @patch('netifaces.ifaddresses',
           new=Mock(return_value=Mock(get=Mock(
               return_value=[{'addr': '10.0.0.1'}]))))
    def test_create_vm_with_getting_network_id_and_name(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - call get_network_id and get_network_name

        Expected: vm has been created
        """
        with patch('core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(return_value=Mock(
                get=Mock(
                    return_value=[{'tenant_id': 1,
                                   'cidr': '10.0.0.0/24',
                                   'network_id': 1,
                                   'id': 1}]))),
                list_networks=Mock(return_value=Mock(
                    get=Mock(return_value=[{'id': 1, 'name': 'Local-Net'}]))))

            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 1)

    def test_exception_in_get_network_id(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - exception in get_network_id

        Expected: vm has not been created
        """
        with patch('core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(
                return_value=Mock(get=Mock(side_effect=Exception(
                    'Exception in get_network_id')))))
            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 0)

    def test_exception_in_get_network_name(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - exception in get_network_name

        Expected: vm has not been created
        """
        with patch('core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(
                return_value=Mock(get=Mock(
                    return_value=[{'tenant_id': 1,
                                   'cidr': '10.0.0.0/24',
                                   'network_id': 1,
                                   'id': 1}]))),
                list_networks=Mock(side_effect=Exception(
                    'Exception in get_network_name')))
            self.pool.add(self.platform)
            self.assertEqual(self.pool.count(), 0)

    @patch('vmpool.clone.OpenstackClone.get_network_id',
           new=Mock(return_value=None))
    def test_none_param_for_get_network_name(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - get_network_id returned None like in case with KeyError in method
        - call get_network_name(None)

        Expected: vm has not been created
        """
        self.pool.add(self.platform)
        self.assertEqual(self.pool.count(), 0)


@patch.multiple(
    'vmpool.clone.OpenstackClone',
    get_network_name=Mock(return_value='Local-Net'),
    get_network_id=Mock(return_value=1)
)
@patch.multiple(
    'core.utils.openstack_utils',
    neutron_client=Mock(return_value=Mock()),
    nova_client=Mock(return_value=Mock()),
    glance_client=Mock(return_value=Mock())
)
class TestOpenstackPlatforms(BaseTestCase):
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
            neutron_client=Mock(return_value=Mock()),
            nova_client=Mock(return_value=Mock()),
            glance_client=Mock(return_value=Mock())
        ), patch.multiple(
            'vmpool.platforms.OpenstackPlatforms',
            images=Mock(return_value=[self.mocked_image]),
            flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
            limits=Mock(return_value={
                'maxTotalCores': 10, 'maxTotalInstances': 10,
                'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
                'totalInstancesUsed': 0, 'totalRAMUsed': 0})
        ):
            from vmpool.virtual_machines_pool import pool
            self.pool = pool

            from vmpool.platforms import Platforms
            self.platforms = Platforms()

    def tearDown(self):
        self.pool.free()
        del self.pool
        self.platforms.cleanup()

    @patch(
        'vmpool.platforms.OpenstackPlatforms.limits',
        new=Mock(return_value={'totalInstancesUsed': 10,
                               'maxTotalInstances': 10})
    )
    def test_limit_instances(self):
        """
        - call OpenstackClone.create()
        - maximum instances already in use

        Expected: CreationException
        """
        count_before_try = self.pool.count()
        self.assertRaises(CreationException, self.pool.add, self.platform)
        self.assertEqual(self.pool.count(), count_before_try)

    @patch(
        'vmpool.platforms.OpenstackPlatforms.limits',
        new=Mock(return_value={'totalInstancesUsed': 0,
                               'maxTotalInstances': 1,
                               'maxTotalCores': 1,
                               'totalCoresUsed': 1,
                               })
    )
    def test_limit_cpu_cores(self):
        """
        - call OpenstackClone.create()
        - maximum cpu cores already in use

        Expected: CreationException
        """
        count_before_try = self.pool.count()
        self.assertRaises(CreationException, self.pool.add, self.platform)
        self.assertEqual(self.pool.count(), count_before_try)

    @patch(
        'vmpool.platforms.OpenstackPlatforms.limits',
        new=Mock(return_value={'totalInstancesUsed': 0,
                               'maxTotalInstances': 1,
                               'maxTotalCores': 2,
                               'totalCoresUsed': 0,
                               'maxTotalRAMSize': 1000,
                               'totalRAMUsed': 1000
                               })
    )
    def test_limit_ram(self):
        """
        - call OpenstackClone.create()
        - maximum RAM already in use

        Expected: CreationException
        """
        count_before_try = self.pool.count()
        self.assertRaises(CreationException, self.pool.add, self.platform)
        self.assertEqual(self.pool.count(), count_before_try)

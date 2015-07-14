# coding: utf-8

import unittest

from mock import Mock, patch, PropertyMock
from vmmaster.core.config import setup_config
from vmmaster.core.utils import openstack_utils

from helpers import wait_for
from vmmaster.core.virtual_machine.virtual_machines_pool import pool


# mocking for Openstack
def custom_wait(self, method):
    self.ready = True


@patch('vmmaster.core.virtual_machine.virtual_machines_pool.'
       'VirtualMachinesPool.can_produce',
       new=Mock(return_value=True))
@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_network_name',
       new=Mock(return_value='Local-Net'))
@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_network_id',
       new=Mock(return_value=1))
@patch('vmmaster.core.db.database', new=Mock())
class TestOpenstackClone(unittest.TestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')

        mocked_image = Mock(id=1, status='active',
                            get=Mock(return_value='snapshot'),
                            min_disk=20,
                            min_ram=2,
                            instance_type_flavorid=1)
        type(mocked_image).name = PropertyMock(return_value='test_origin_1')

        openstack_utils.nova_client = Mock()
        openstack_utils.neutron_client = Mock()
        openstack_utils.glance_client = Mock()
        openstack_utils.glance_client().images.list = Mock(
            return_value=[mocked_image])

        with patch('vmmaster.core.db.database',
                   new=Mock(add=Mock(), update=Mock())):
            from vmmaster.core.platforms import Platforms
            Platforms()
        self.platform = "origin_1"

    def tearDown(self):
        with patch('vmmaster.core.db.database',
                   new=Mock(add=Mock(), update=Mock())):
            pool.free()

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service', new=custom_wait)
    def test_creation_vm(self):
        """
        test_creation_vm
        - call OpenstackClone.create()
        - _wait_for_activated_service has been mocked

        Expected: vm has been created
        """
        pool.add(self.platform)
        self.assertTrue(pool.using[0].ready)
        self.assertEqual(len(pool.using), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service', new=custom_wait)
    @patch('vmmaster.core.db.database', new=Mock())
    def test_exception_during_creation_vm(self):
        """
        test_exception_during_creation_vm
        - call OpenstackClone.create()
        - exception in create()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(
                servers=Mock(create=Mock(
                    side_effect=Exception('Exception in create'))))

            pool.add(self.platform)
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=False))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.rebuild',
           new=Mock(return_value=True))
    def test_e_in_wait_for_activated_service_and_vm_has_not_been_created(self):
        """
        test_e_in_wait_for_activated_service_and_vm_has_not_been_created
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is False

        Expected: vm has been rebuilded
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))

            pool.add(self.platform)
            self.assertEqual(pool.count(), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=False))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    def test_exception_in_wait_for_activated_service_and_rebuild_failed(self):
        """
        test_exception_in_wait_for_activated_service_and_rebuild_failed
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is False
        - call rebuild() and raise Exception in rebuild()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))

            pool.add(self.platform)
            wait_for(lambda: pool.count() == 0)
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock())
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    def test_exception_in_wait_for_activated_service_and_ping_success(self):
        """
        test_exception_in_wait_for_activated_service_and_ping_success
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is True
        - ping success

        Expected: vm has been created
        """
        with \
                patch('vmmaster.core.db.database'),\
                patch('vmmaster.core.utils.openstack_utils.nova_client')\
                as nova:
            nova.return_value = Mock(
                servers=Mock(
                    find=Mock(side_effect=Exception(
                        'Exception in _wait_for_activated_service'))))
            pool.add(self.platform)

            wait_for(lambda: pool.using[0].ready is True)
            self.assertEqual(pool.count(), 1)
            self.assertTrue(pool.using[0].ready)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock())
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.rebuild',
           new=Mock(return_value=True))
    # @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
    #        new=Mock(return_value=False))
    # @patch('vmmaster.core.db.database', new=Mock())
    def test_exception_in_wait_for_activated_service_and_ping_failed(self):
        """
        test_exception_in_wait_for_activated_service_and_ping_failed
        - call OpenstackClone.create()
        - exception in _wait_for_activated_service
        - vm_has_created is True
        - ping failed

        Expected: vm has been rebuilded
        """
        # with patch('vmmaster.core.db.database', new=Mock()), \
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova,\
                patch('vmmaster.core.virtual_machine.clone.'
                      'OpenstackClone.ping_vm') as ping_mock:
            nova.return_value = Mock(servers=Mock(
                find=Mock(side_effect=Exception(
                    'Exception in _wait_for_activated_service'))))
            ping_mock.return_value = False

            pool.add(self.platform)
            self.assertEqual(pool.count(), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service', new=custom_wait)
    def test_exception_in_getting_image(self):
        """
        test_exception_in_getting_image
        - call OpenstackClone.create()
        - exception in OpenstackClone.image

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(create=Mock()),
                                     images=Mock(
                                         find=Mock(side_effect=Exception(
                                             'Exception in image'))))

            pool.add(self.platform)
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.image',
           new=Mock())
    def test_exception_in_getting_flavor(self):
        """
        test_exception_in_getting_flavor
        - call OpenstackClone.create()
        - exception in OpenstackClone.flavor

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(create=Mock()),
                                     flavors=Mock(
                                         find=Mock(side_effect=Exception(
                                             'Exception in flavor'))))

            pool.add(self.platform)
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    def test_delete_vm(self):
        """
        test_delete_vm
        - call OpenstackClone.create()
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.add(self.platform)
            pool.using[0].delete()
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=False))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    def test_delete_vm_if_vm_does_not_exist(self):
        """
        test_delete_vm_if_vm_does_not_exist
        - call OpenstackClone.create()
        - check_vm_exist is False
        - call OpenstackClone.delete()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.add(self.platform)
            pool.using[0].delete()
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    def test_rebuild_preload_vm(self):
        """
        test_rebuild_preload_vm
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.preload(self.platform, prefix='preloaded')
            wait_for(lambda: pool.pool[0].ready is True)
            pool.pool[0].rebuild()
            wait_for(lambda: pool.pool[0].ready is True)
            self.assertEqual(pool.count(), 1)
            self.assertTrue(pool.pool[0].ready)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    @patch('vmmaster.core.db.database', new=Mock())
    def test_rebuild_ondemand_vm(self):
        """
        test_rebuild_ondemand_vm
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.add(self.platform, prefix='ondemand')
            wait_for(lambda: pool.using[0].ready is True)
            pool.using[0].rebuild()
            wait_for(lambda: pool.using[0].ready is True)
            self.assertEqual(pool.count(), 1)
            self.assertTrue(pool.using[0].ready)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock(__name__='get_ip'))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    def test_rebuild_ondemand_vm_with_wait_activate_service(self):
        """
        test_rebuild_ondemand_vm_with_wait_activate_service
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.add(self.platform, prefix='ondemand')
            wait_for(lambda: pool.using[0].ready is True)
            pool.using[0].rebuild()
            wait_for(lambda: pool.using[0].ready is True)
            self.assertEqual(pool.count(), 1)
            self.assertTrue(pool.using[0].ready)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock(__name__='get_ip'))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    def test_rebuild_preload_vm_with_wait_activate_service(self):
        """
        test_rebuild_preload_vm_with_wait_activate_service
        - call OpenstackClone.create()
        - call OpenstackClone.rebuild()

        Expected: vm has been rebuilded and added in pool
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock()))))

            pool.preload(self.platform, prefix='preloaded')
            wait_for(lambda: pool.pool[0].ready is True)
            pool.pool[0].rebuild()
            wait_for(lambda: pool.pool[0].ready is True)
            self.assertEqual(pool.count(), 1)
            self.assertTrue(pool.pool[0].ready)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=False))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    def test_rebuild_vm_if_vm_does_not_exist(self):
        """
        test_rebuild_vm_if_vm_does_not_exist
        - call OpenstackClone.create()
        - check_vm_exist is False
        - call OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            pool.add(self.platform)
            wait_for(lambda: pool.using[0].ready is True)
            pool.using[0].rebuild()
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.'
           '_wait_for_activated_service',
           new=custom_wait)
    def test_exception_in_rebuild_vm_if_vm_exist(self):
        """
        test_exception_in_rebuild_vm_if_vm_exist
        - call OpenstackClone.create()
        - check_vm_exist is True
        - exception in OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(delete=Mock(), rebuild=Mock(
                    side_effect=Exception('Rebuild error'))))))

            pool.add(self.platform)
            wait_for(lambda: pool.using[0].ready is True)
            pool.using[0].rebuild()
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock())
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.rebuild',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    def test_exception_in_vm_has_created(self):
        """
        test_exception_in_vm_has_created
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - exception in vm_has_created()

        Expected: vm has been rebuilded
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(
                servers=Mock(find=Mock(side_effect=Exception(
                    'Exception in vm_has_created'))))

            pool.add(self.platform)
            self.assertEqual(pool.count(), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
           new=Mock(__name__='get_ip'))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    def test_vm_in_build_status(self):
        """
        test_vm_in_build_status
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - first call server.status.lower() return 'build',
          second call return 'active'
        Expected: vm has been created
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(status=Mock(lower=Mock(
                    side_effect=['build', 'active']))))))
            pool.add(self.platform)
            self.assertEqual(pool.count(), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    def test_exception_in_get_ip(self, ):
        """
        test_exception_in_get_ip
        - call OpenstackClone.create()
        - check_vm_exist is True
        - exception in Openstack.get_ip()
        - exception in OpenstackClone.rebuild()

        Expected: vm has been deleted
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova,\
                patch('vmmaster.core.virtual_machine.clone.'
                      'OpenstackClone.ping_vm') as ping_mock:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(addresses=Mock(
                    get=Mock(side_effect=Exception('Error get addresses'))),
                    rebuild=Mock(side_effect=Exception('Rebuild exception')))))
            )
            ping_mock.side_effect = False
            pool.add(self.platform)
            wait_for(lambda: pool.count() > 0)
            self.assertEqual(pool.count(), 1)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
           new=Mock(return_value=True))
    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
           new=Mock(return_value=True))
    def test_create_vm_with_get_ip(self):
        """
        test_create_vm_with_get_ip
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - get_ip return mocked ip address and mac

        Expected: vm has been created
        """
        with patch('vmmaster.core.utils.openstack_utils.nova_client') as nova:
            nova.return_value = Mock(servers=Mock(find=Mock(
                return_value=Mock(addresses=Mock(get=Mock(
                    return_value=[{'addr': '127.0.0.1',
                                   'OS-EXT-IPS-MAC:mac_addr': 'test_mac'}])))))
            )
            pool.add(self.platform)
            wait_for(lambda: pool.using[0].ready is True)
            self.assertEqual(pool.using[0].ip, '127.0.0.1')
            self.assertEqual(pool.using[0].mac, 'test_mac')
            self.assertEqual(pool.count(), 1)


@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.check_vm_exist',
       new=Mock(return_value=False))
@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.ping_vm',
       new=Mock(return_value=True))
@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.vm_has_created',
       new=Mock(return_value=True))
@patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_ip',
       new=Mock(__name__='get_ip'))
@patch('vmmaster.core.virtual_machine.virtual_machines_pool.'
       'VirtualMachinesPool.can_produce',
       new=Mock(return_value=True))
@patch('vmmaster.core.db.database', Mock(add=Mock(), update=Mock()))
class TestNetworkGetting(unittest.TestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')

        mocked_image = Mock(
            id=1, status='active', get=Mock(
                return_value='snapshot'),
            min_disk=20, min_ram=2, instance_type_flavorid=1)
        type(mocked_image).name = PropertyMock(return_value='test_origin_1')
        openstack_utils.nova_client = Mock()
        openstack_utils.neutron_client = Mock()
        openstack_utils.glance_client = Mock()
        openstack_utils.glance_client().images.list = Mock(
            return_value=[mocked_image])

        with patch('vmmaster.core.db.database', new=Mock()):
            from vmmaster.core.platforms import Platforms
            Platforms()
        self.platform = "origin_1"

    def tearDown(self):
        with patch('vmmaster.core.db.database', new=Mock()):
            pool.free()

    @patch('netifaces.ifaddresses',
           new=Mock(return_value=Mock(get=Mock(
               return_value=[{'addr': '10.0.0.1'}]))))
    def test_create_vm_with_getting_network_id_and_name(self):
        """
        test_create_vm_with_getting_network_id_and_name
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - call get_network_id and get_network_name

        Expected: vm has been created
        """
        with patch('vmmaster.core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(return_value=Mock(
                get=Mock(
                    return_value=[{'tenant_id': 1,
                                   'cidr': '10.0.0.0/24',
                                   'network_id': 1,
                                   'id': 1}]))),
                list_networks=Mock(return_value=Mock(
                    get=Mock(return_value=[{'id': 1, 'name': 'Local-Net'}]))))
            pool.add(self.platform)
            self.assertEqual(pool.count(), 1)

    def test_exception_in_get_network_id(self):
        """
        test_exception_in_get_network_id
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - exception in get_network_id

        Expected: vm has not been created
        """
        with patch('vmmaster.core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(
                return_value=Mock(get=Mock(side_effect=Exception(
                    'Exception in get_network_id')))))
            pool.add(self.platform)
            self.assertEqual(pool.count(), 0)

    def test_exception_in_get_network_name(self):
        """
        test_exception_in_get_network_name
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - exception in get_network_name

        Expected: vm has not been created
        """
        with patch('vmmaster.core.utils.openstack_utils.neutron_client') \
                as nova:
            nova.return_value = Mock(list_subnets=Mock(
                return_value=Mock(get=Mock(
                    return_value=[{'tenant_id': 1,
                                   'cidr': '10.0.0.0/24',
                                   'network_id': 1,
                                   'id': 1}]))),
                list_networks=Mock(side_effect=Exception(
                    'Exception in get_network_name')))
            pool.add(self.platform)
            self.assertEqual(pool.count(), 0)

    @patch('vmmaster.core.virtual_machine.clone.OpenstackClone.get_network_id',
           new=Mock(return_value=None))
    def test_none_param_for_get_network_name(self):
        """
        test_none_param_for_get_network_name
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - vm_has_created is True
        - get_network_id returned None like in case with KeyError in method
        - call get_network_name(None)

        Expected: vm has not been created
        """
        pool.add(self.platform)
        self.assertEqual(pool.count(), 0)

# coding: utf-8

from tests.unit.helpers import BaseTestCase
from mock import Mock, patch
from core.config import setup_config


@patch.multiple(
    'vmpool.clone.OpenstackClone',
    get_network_name=Mock(return_value='Local-Net')
)
@patch.multiple(
    'core.utils.openstack_utils',
    neutron_client=Mock(return_value=Mock()),
    nova_client=Mock(return_value=Mock()),
    glance_client=Mock(return_value=Mock())
)
class TestOpenstackCloneUnit(BaseTestCase):
    def setUp(self):
        setup_config('data/config_openstack.py')
        self.mocked_origin = Mock(short_name="platform_1")
        self.pool = Mock(
            pool=dict(),
            using=dict()
        )

    def test_success_openstack_set_userdata(self):
        from vmpool.clone import OpenstackClone
        clone = OpenstackClone(self.mocked_origin, "preloaded", self.pool)
        file_object = clone.set_userdata()
        self.assertTrue(hasattr(file_object, "read"))

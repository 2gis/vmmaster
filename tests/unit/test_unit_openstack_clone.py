# coding: utf-8

import os
from tests.unit.helpers import BaseTestCase
from mock import Mock, patch
from core.config import setup_config


@patch.multiple(
    'core.utils.openstack_utils',
    nova_client=Mock(return_value=Mock())
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
        file_object = clone.set_userdata(
            "%s/data/userdata" % os.path.dirname(__file__)
        )
        self.assertTrue(hasattr(file_object, "read"))

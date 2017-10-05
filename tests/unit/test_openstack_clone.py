# coding: utf-8

import os
from mock import Mock, patch, PropertyMock

from tests.helpers import BaseTestCase, custom_wait, wait_for, DatabaseMock
from core.db.models import Provider


class TestOpenstackCloneUnit(BaseTestCase):
    def setUp(self):
        from flask import Flask
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        self.app = Flask(__name__)
        self.app.database = DatabaseMock()

        self.pool = Mock(id=1, provider=Provider(name='fake', url='no//url'))
        self.mocked_origin = Mock(
            short_name="platform_1",
            id=1, status="active",
            get=Mock(return_value="snapshot"),
            min_disk=20,
            min_ram=2,
            instance_type_flavorid=1
        )

        self.ctx = self.app.app_context()
        self.ctx.push()

        with patch(
            "core.utils.openstack_utils.nova_client", Mock(return_value=Mock())
        ), patch(
            "flask.current_app", self.app
        ):
            from vmpool.clone import OpenstackClone
            self.clone = OpenstackClone(self.mocked_origin, "preloaded", self.pool)

    def tearDown(self):
        self.ctx.pop()
        del self.app

    def test_success_openstack_set_userdata(self):
        file_object = self.clone.set_userdata("%s/data/userdata" % os.path.dirname(__file__))
        self.assertTrue(hasattr(file_object, "read"))

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        _wait_for_activated_service=custom_wait,
    )
    def test_creation_vm(self):
        """
        - call OpenstackClone.create()
        - _wait_for_activated_service has been mocked

        Expected: vm has been created
        """
        self.clone.create()
        self.assertTrue(self.clone.nova_client.servers.create.called)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        get_vm=Mock(return_value=None),
        delete=Mock(),
    )
    def test_exception_in_wait_for_activated_service(self):
        """
        - call OpenstackClone.create()
        - get_vm() return None

        Expected: vm has been deleted
        """
        self.clone.create()
        wait_for(lambda: self.clone.delete.called)
        self.assertTrue(self.clone.delete.called)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        get_ip=Mock(),
        get_vm=Mock(return_value=Mock(status="active")),
        ping_vm=Mock(return_value=True),
    )
    def test_ping_success(self):
        """
        - call OpenstackClone.create()
        - ping success

        Expected: vm has been created
        """
        self.clone.create()
        wait_for(lambda: self.clone.ready)
        self.assertTrue(self.clone.ready)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        get_ip=Mock(),
        get_vm=Mock(return_value=Mock(status="active")),
        rebuild=Mock(),
        ping_vm=Mock(return_value=False),
    )
    def test_exception_in_wait_for_activated_service_and_ping_failed(self):
        """
        - call OpenstackClone.create()
        - is_active is True
        - ping failed

        Expected: vm has been rebuilded
        """
        self.clone.create()
        wait_for(lambda: self.clone.rebuild.called)
        self.assertTrue(self.clone.rebuild.called)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        image=PropertyMock(side_effect=Exception("Exception in image")),
    )
    def test_exception_in_getting_image(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.image

        Expected: Exception was raised
        """
        with self.assertRaises(Exception):
            self.clone.create()

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        flavor=PropertyMock(side_effect=Exception("Exception in flavor")),
    )
    def test_exception_in_getting_flavor(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.flavor

        Expected: Exception was raised
        """
        with self.assertRaises(Exception):
            self.clone.create()

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        get_vm=Mock(status="active", delete=Mock(), rebuild=Mock()),
    )
    def test_delete_vm(self):
        """
        - call OpenstackClone.delete(try_to_rebuild=False)

        Expected: vm has been deleted
        """
        self.clone.delete()
        self.assertTrue(self.clone.get_vm.return_value.delete)
        self.assertTrue(self.clone.deleted)
        self.assertFalse(self.clone.ready)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        get_vm=Mock(return_value=None),
        _wait_for_activated_service=custom_wait,
    )
    def test_rebuild_after_delete_vm_if_vm_does_not_exist(self):
        """
        - get_vm return None
        - call OpenstackClone.delete(try_to_rebuild=True)

        Expected: vm has not been deleted
        """
        self.clone.delete(try_to_rebuild=True)
        wait_for(lambda: self.clone.ready is False)
        self.assertIsNone(self.clone.deleted)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        _wait_for_activated_service=custom_wait,
        get_vm=Mock(status="active", delete=Mock(), rebuild=Mock()),
    )
    def test_rebuild_preload_vm(self):
        """
        - call OpenstackClone.delete(try_to_rebuild=True)

        Expected: vm has been rebuilded and added in pool
        """
        self.clone.delete(try_to_rebuild=True)
        wait_for(lambda: self.clone.ready is True)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        _wait_for_activated_service=custom_wait,
        get_vm=Mock(return_value=Mock(
            delete=Mock(), rebuild=Mock(side_effect=Exception("Rebuild error")), status="active")
        ),
    )
    def test_exception_in_rebuild_vm_if_vm_exist(self):
        """
        - call OpenstackClone.create()
        - exception in OpenstackClone.delete(try_to_rebuild=True)

        Expected: vm has been deleted
        """
        self.clone.delete(try_to_rebuild=True)
        wait_for(lambda: self.clone.ready is False)
        self.assertTrue(self.clone.deleted)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        ping_vm=Mock(return_value=True),
        get_vm=Mock(return_value=Mock(
            rebuild=Mock(return_value=True),
            status=Mock(lower=Mock(side_effect=["build", "error", "active"])))
        ),
        get_ip=Mock(),
    )
    def test_vm_in_error_status(self):
        """
        - call OpenstackClone.create()
        - first call server.status.lower() return "build",
          second call return "error"
          third call return "active"
        Expected: vm has been rebuilded
        """
        self.clone.create()
        wait_for(lambda: self.clone.ready is True)
        self.assertTrue(self.clone.ready)

    @patch.multiple(
        "vmpool.clone.OpenstackClone",
        ping_vm=Mock(return_value=True),
        is_created=Mock(return_value=True),
        ip="127.0.0.1",
        get_vm=Mock(
            return_value=Mock(
                status="active",
            )
        ),
    )
    def test_create_vm_with_get_ip(self):
        """
        - call OpenstackClone.create()
        - check_vm_exist is True
        - ping successful
        - ready is True
        - get_ip return mocked ip address and mac

        Expected: vm has been created
        """
        self.clone.create()
        wait_for(lambda: self.clone.ready is True)
        self.assertEqual(self.clone.ip, "127.0.0.1")

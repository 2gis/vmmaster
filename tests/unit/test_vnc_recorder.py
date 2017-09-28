# coding: utf-8

from flask import Flask
from mock import patch, Mock
from tests.helpers import BaseTestCase, DatabaseMock, wait_for


@patch.multiple(
    "core.db.models.Endpoint",
    set_provider=Mock(),
    set_platform=Mock()
)
@patch('core.utils.openstack_utils.nova_client', Mock())
class TestVNCVideoHelper(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        cls.app = Flask(__name__)
        cls.app.database = DatabaseMock()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_run_recorder(self):
        """
        - call session.run()
        - call session.delete()

        Expected: vnc_recorder was started and stopped
        """
        dc = {
            'takeScreencast': True,
            'platform': 'test_origin_1'
        }

        with patch(
            'flask.current_app', self.app
        ), patch(
            'core.db.Database', DatabaseMock()
        ), patch(
            'core.video.VNCVideoHelper._flvrec', Mock()
        ), patch(
            'core.video.VNCVideoHelper.start_recording', Mock()
        ) as start_rec_mock, patch(
            'core.video.VNCVideoHelper.stop', Mock()
        ) as stop_rec_mock:
            from core.sessions import Session
            from vmpool.virtual_machines_pool import VirtualMachinesPool
            from vmpool.clone import Clone

            session = Session(dc=dc)
            session.name = "session1"
            session.id = 1

            self.app.sessions = Mock(get_session=Mock(return_value=session))
            self.app.database.active_sessions["1"] = session
            self.app.pool = VirtualMachinesPool(self.app, platforms_class=Mock(), preloader_class=Mock(),
                                                matcher_class=Mock())

            endpoint = Clone(Mock(
                short_name="platform_1",
                id=1, status="active",
                get=Mock(return_value="snapshot"),
                min_disk=20,
                min_ram=2,
                instance_type_flavorid=1
            ), "ondemand", self.app.pool)
            endpoint.ip = '127.0.0.1'

            session.endpoint = endpoint
            session.run()
            wait_for(lambda: self.app.pool.artifact_collector.in_queue, timeout=5)

            session.succeed()
            self.assertTrue(session.closed)

            wait_for(lambda: not self.app.pool.artifact_collector.in_queue, timeout=5)
            self.assertTrue(start_rec_mock.called)
            self.assertTrue(stop_rec_mock.called)

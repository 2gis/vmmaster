# coding: utf-8

from flask import Flask
from mock import patch, Mock, PropertyMock
from tests.helpers import BaseTestCase, DatabaseMock, wait_for


class TestVNCVideoHelper(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        cls.app = Flask(__name__)
        cls.app.database = DatabaseMock()

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_run_recorder(self):
        """
        - call session.run()
        - call session.succeed()

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
        ) as stop_rec_mock, patch(
            'core.video.VNCVideoHelper.is_alive', Mock(return_value=True)
        ):
            from core.db.models import Session, Endpoint
            from vmpool.virtual_machines_pool import VirtualMachinesPool

            session = Session(platform='some_platform', dc=dc)
            session.name = "session1"
            session.id = 1

            self.app.pool = VirtualMachinesPool(self.app, platforms_class=Mock(), preloader_class=Mock())
            self.app.pool.provider = PropertyMock(id=1)

            endpoint = Endpoint(origin=Mock(), prefix="ondemand", provider=self.app.pool.provider)
            endpoint.ip = '127.0.0.1'

            session.endpoint = endpoint
            session.run()
            wait_for(lambda: self.app.pool.artifact_collector.in_queue, timeout=5)

            session.succeed()
            self.assertTrue(session.closed)

            wait_for(lambda: not self.app.pool.artifact_collector.in_queue, timeout=5)
            self.assertTrue(start_rec_mock.called)
            self.assertTrue(stop_rec_mock.called)

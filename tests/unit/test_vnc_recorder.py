# coding: utf-8

from flask import Flask
from mock import patch, Mock
from tests.unit.helpers import BaseTestCase, DatabaseMock, wait_for
from multiprocessing import Process


@patch('core.utils.openstack_utils.nova_client', Mock())
class TestVNCVideoHelper(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from core.config import setup_config
        setup_config('data/config_openstack.py')

        cls.app = Flask(__name__)
        cls.app.database = DatabaseMock()
        cls.app.sessions = Mock()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('flask.current_app', Mock())
    @patch('flask.current_app.database', Mock())
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
            'core.db.Database', DatabaseMock()
        ):
            from core.sessions import Session
            session = Session(dc=dc)
            session.name = "session1"
            with patch(
                'core.video.VNCVideoHelper._flvrec', Mock()
            ):
                from vmpool import VirtualMachine
                endpoint = VirtualMachine(name='test_endpoint', platform='test_origin_1')
                endpoint.ip = '127.0.0.1'
                endpoint.save_artifacts = Mock()
                session.run(endpoint=endpoint)
                self.assertTrue(
                    isinstance(session.endpoint.vnc_helper.recorder, Process))

                session.close()
                self.assertTrue(wait_for(
                    lambda: not session.endpoint.vnc_helper.recorder.is_alive()))

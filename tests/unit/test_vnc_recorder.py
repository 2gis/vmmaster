# coding: utf-8

from flask import Flask
from mock import patch, Mock
from tests.unit.helpers import BaseTestCase, DatabaseMock, wait_for
from multiprocessing import Process


class TestVNCVideoHelper(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from core.config import setup_config
        setup_config('data/config.py')

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
        endpoint = Mock(ip='127.0.0.1', name='test_endpoint')

        dc = {
            'takeScreencast': True,
            'platform': 'test_origin_1'
        }

        with patch(
            'core.db.models.Session', Mock()
        ), patch(
            "core.network.Network", Mock()
        ), patch(
            "core.connection.Virsh", Mock()
        ), patch(
            'core.db.Database', DatabaseMock()
        ):
            from core.sessions import Session
            self.session = Session(dc=dc)
            self.session.name = "session1"
            with patch(
                'core.video.VNCVideoHelper._flvrec', Mock()
            ), patch(
                'core.video.VNCVideoHelper._flv2webm', Mock()
            ):
                self.session.run(endpoint=endpoint)
                self.assertTrue(
                    isinstance(self.session.vnc_helper.recorder, Process))

                self.session.close()
                self.assertTrue(wait_for(
                    lambda: not self.session.vnc_helper.recorder.is_alive()))

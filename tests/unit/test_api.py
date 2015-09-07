# coding: utf-8

import json
from datetime import datetime
from mock import Mock, patch
from helpers import BaseTestCase, fake_home_dir
from lode_runner import dataprovider


class TestApi(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config.py')

        with patch('core.network.network.Network',
                   Mock(name='Network')), \
                patch('core.connection.Virsh', Mock(name='Virsh')), \
                patch('core.db.database', Mock()), \
                patch('core.utils.init.home_dir',
                      Mock(return_value=fake_home_dir())), \
                patch('core.logger.setup_logging',
                      Mock(return_value=Mock())),\
                patch('core.sessions.SessionWorker', Mock()):

            from vmmaster.server import create_app
            self.app = create_app()

        self.vmmaster_client = self.app.test_client()
        self.platforms = self.app.platforms.platforms
        self.platform = sorted(self.platforms.keys())[0]

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def tearDown(self):
        with patch('core.db.database', Mock()) as db:
            db.update = Mock()
            self.app.cleanup()
            del self.app

    @patch('core.endpoints.delete', new=Mock())
    @patch('core.db.database', new=Mock())
    def test_api_sessions(self):
        from core.sessions import Session
        session = Session()
        session.id = 1
        session.name = "session1"
        session.platform = 'test_origin_1'
        session.created = session.modified = datetime.now()

        with patch('core.db.database.get_sessions',
                   Mock(return_value=[session])):
            response = self.vmmaster_client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        sessions = body['result']['sessions']
        self.assertEqual(1, len(sessions))
        self.assertEqual(self.platform, sessions[0]['platform'])
        self.assertEqual(200, body['metacode'])

        session.failed()

    def test_api_platforms(self):
        response = self.vmmaster_client.get('/api/platforms')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        platforms = body['result']['platforms']
        self.assertEqual(2, len(platforms))
        names = [platform for platform in self.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    @patch('core.endpoints.delete', new=Mock())
    @patch('core.db.database', Mock())
    def test_api_stop_session(self):
        from core.sessions import Session
        session = Session()
        session.id = 1
        session.failed = Mock()

        with patch('core.db.database.get_session',
                   Mock(return_value=session)):
            response = self.vmmaster_client.post("/api/session/%s/stop"
                                                 % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])
        session.failed.assert_any_call()

    @patch('core.db.database', Mock())
    def test_get_screenshots(self):

        steps = [
            Mock(screenshot=None),
            Mock(screenshot="/vmmaster/screenshots/1/1.png")
        ]

        with patch('core.db.database.get_log_steps_for_session',
                   Mock(return_value=steps)):
            response = self.vmmaster_client.get('/api/session/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(1, len(screenshots))
        self.assertEqual(200, body['metacode'])

    @dataprovider([
        ("/vmmaster/screenshots/1/1.png", 1),
        (None, 0)
    ])
    @patch('core.db.database', Mock())
    def test_get_screenshot_for_step(self, screenshot_path, screenshots_count):

        steps = Mock(screenshot=screenshot_path)

        with patch('core.db.database.get_step_by_id',
                   Mock(return_value=steps)):
            response = self.vmmaster_client.get(
                '/api/session/1/step/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(screenshots_count, len(screenshots))
        self.assertEqual(200, body['metacode'])

    @patch('core.db.database', Mock())
    def test_get_screenshots_for_label(self):

        steps = [
            Mock(control_line="POST /wd/hub/session/23/element HTTP/1.0",
                 id=2,
                 screenshot="/vmmaster/screenshots/1/1.png"),
            Mock(control_line="POST /wd/hub/session/23/vmmasterLabel HTTP/1.0",
                 id=1,
                 screenshot=None)
        ]

        with patch('core.db.database.get_log_steps_for_session',
                   Mock(return_value=steps)):
            response = \
                self.vmmaster_client.get('/api/session/1/label/1/screenshots')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        screenshots = body['result']['screenshots']
        self.assertEqual(1, len(screenshots))
        self.assertEqual(200, body['metacode'])

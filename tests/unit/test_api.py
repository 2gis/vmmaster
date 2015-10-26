# coding: utf-8

import json
from datetime import datetime
from mock import Mock, patch
from multiprocessing import Process
from helpers import BaseTestCase, fake_home_dir, DatabaseMock, wait_for
from lode_runner import dataprovider


class TestApi(BaseTestCase):
    def setUp(self):
        from core.config import setup_config
        setup_config('data/config.py')

        with patch(
            'core.network.Network', Mock(name='Network')
        ), patch(
            'core.connection.Virsh', Mock(name='Virsh')
        ), patch(
            'core.db.database', DatabaseMock()
        ), patch(
            'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
        ), patch(
            'core.logger.setup_logging', Mock(return_value=Mock())
        ), patch(
            'core.sessions.SessionWorker', Mock()
        ):
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

        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.app.sessions.kill_all()
        self.ctx.pop()
        with patch('core.db.database'):
            self.app.cleanup()
            del self.app

    def test_api_sessions(self):
        from core.sessions import Session
        session = Session()
        session.name = "session1"
        session.platform = 'test_origin_1'
        session.created = session.modified = datetime.now()

        with patch('flask.current_app.sessions.active',
                   Mock(return_value=[session])):
            response = self.vmmaster_client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        sessions = body['result']['sessions']
        self.assertEqual(1, len(sessions))
        self.assertEqual(self.platform, sessions[0]['platform'])
        self.assertEqual(200, body['metacode'])

        with patch('vmpool.endpoint.delete_vm', new=Mock()):
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

    def test_api_stop_session(self):
        from core.sessions import Session
        session = Session()
        session.failed = Mock()

        with patch(
            'flask.current_app.sessions.get_session',
            Mock(return_value=session)
        ):
            response = self.vmmaster_client.post("/api/session/%s/stop"
                                                 % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])

        with patch('vmpool.endpoint.delete_vm', new=Mock()):
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

    @patch('core.db.database', Mock())
    def test_failed_get_vnc_info_with_create_proxy(self):
        from core.sessions import Session
        endpoint = Mock(ip='127.0.0.1')
        session = Session()
        session.name = "session1"
        session.platform = 'test_origin_1'
        session.created = session.modified = datetime.now()

        expected = 5901

        with patch(
                'flask.current_app.sessions.active',
                Mock(return_value=[session])
        ), patch(
                'websockify.websocketproxy.websockify_init', Mock()
        ):
            session.run(endpoint)
            response = self.vmmaster_client.get(
                '/api/session/%s/vnc_info' % session.id)

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']['vnc_proxy_port']
        self.assertEqual(type(expected), type(vnc_proxy_port))
        self.assertEqual(200, body['metacode'])
        self.assertTrue(isinstance(session.vnc_helper.proxy, Process))

        session.delete()
        self.assertTrue(wait_for(lambda: not session.vnc_helper.proxy.is_alive()))

    @patch('core.db.database', Mock())
    def test_get_vnc_info_for_running_proxy(self):
        from core.sessions import Session
        endpoint = Mock(ip='127.0.0.1')
        session = Session()
        session.name = "session1"
        session.platform = 'test_origin_1'
        session.created = session.modified = datetime.now()
        session.run(endpoint)
        session.vnc_helper = Mock(proxy=Mock(),
                                  get_proxy_port=Mock(return_value=5900))

        expected = {
            'vnc_proxy_port': 5900
        }

        with patch(
                'flask.current_app.sessions.active',
                Mock(return_value=[session])
        ):
            response = self.vmmaster_client.get(
                '/api/session/%s/vnc_info' % session.id)

        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']
        self.assertDictEqual(expected, vnc_proxy_port)
        self.assertEqual(200, body['metacode'])
        session.delete()

    @patch('core.db.database', Mock())
    def test_get_vnc_info_if_session_not_found(self):
        with patch(
                'flask.current_app.sessions.active',
                Mock(return_value=[])
        ), patch(
                'websockify.websocketproxy.websockify_init', Mock()
        ), patch(
                'core.utils.network_utils.get_free_port',
                Mock(side_effect=5900)
        ):
            response = self.vmmaster_client.get('/api/session/1/vnc_info')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        vnc_proxy_port = body['result']
        self.assertDictEqual({}, vnc_proxy_port)
        self.assertEqual(500, body['metacode'])
# coding: utf-8

import time
import json
from mock import Mock, patch
from helpers import BaseTestCase, fake_home_dir


class TestApi(BaseTestCase):
    def setUp(self):
        from vmmaster.core.config import setup_config
        setup_config('data/config.py')

        with patch('vmmaster.core.network.network.Network',
                   Mock(name='Network')), \
                patch('vmmaster.core.connection.Virsh', Mock(name='Virsh')), \
                patch('vmmaster.core.db.database', Mock()), \
                patch('vmmaster.core.utils.init.home_dir',
                      Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      Mock(return_value=Mock())),\
                patch('vmmaster.core.sessions.SessionWorker', Mock()):

            from vmmaster.server import create_app
            from vmpool.app import app
            self.app = create_app()
            self.vmpool = app()

        self.vmmaster_client = self.app.test_client()
        self.vmpool_client = self.vmpool.test_client()
        self.platforms = self.vmpool.platforms.platforms
        self.platform = sorted(self.platforms.keys())[0]

        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()) as db:
            db.update = Mock()
            self.app.cleanup()
            self.vmpool.shutdown()
            del self.app
            del self.vmpool

    @patch('vmmaster.core.utils.utils.del_endpoint', new=Mock())
    @patch('vmmaster.core.db.database', new=Mock())
    def test_api_sessions(self):
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1
        session.name = "session1"
        session.platform = 'test_origin_1'
        session.time_created = session.time_modified = time.time()

        with patch('vmmaster.core.db.database.get_sessions',
                   Mock(return_value=[session])):
            response = self.vmmaster_client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)

        sessions = body['result']['sessions']
        self.assertEqual(1, len(sessions))
        self.assertEqual(self.platform, sessions[0]['platform'])
        self.assertEqual(200, body['metacode'])

        session.close()

    def test_api_platforms(self):
        response = self.vmpool_client.get('/api/platforms')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        platforms = body['result']['platforms']
        self.assertEqual(2, len(platforms))
        names = [platform for platform in self.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    @patch('vmmaster.core.utils.utils.del_endpoint', new=Mock())
    @patch('vmmaster.core.db.database', Mock())
    def test_api_stop_session(self):
        from vmmaster.core.sessions import Session
        session = Session()
        session.id = 1
        session.close = Mock()

        with patch('vmmaster.core.db.database.get_session',
                   Mock(return_value=session)):
            response = self.vmmaster_client.post("/api/session/%s/stop"
                                                 % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])
        session.close.assert_any_call()

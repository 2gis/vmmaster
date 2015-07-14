# coding: utf-8

import json
from mock import Mock, patch
from helpers import BaseTestCase, fake_home_dir


# Mocking
def session_id(*args, **kwargs):
    from uuid import uuid4

    class Session(object):
        id = uuid4()
    return Session()

from vmpool import VirtualMachine


class TestApi(BaseTestCase):
    def setUp(self):
        from vmmaster.core.config import setup_config
        setup_config('data/config.py')

        import vmmaster.core.network.network
        import vmmaster.core.connection
        import vmmaster.core.db

        with patch.object(vmmaster.core.network.network, 'Network',
                          new=Mock(name='Network')), \
                patch.object(vmmaster.core.connection, 'Virsh',
                             new=Mock(name='Virsh')), \
                patch.object(vmmaster.core.db, 'database',
                             new=Mock(create_session=Mock(
                                      side_effect=session_id))), \
                patch('vmmaster.core.utils.init.home_dir',
                      new=Mock(return_value=fake_home_dir())), \
                patch('vmmaster.core.logger.setup_logging',
                      new=Mock(return_value=Mock())):
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
        from vmmaster.webdriver.commands import DesiredCapabilities
        dc1 = DesiredCapabilities(name="session1",
                                  platform='test_origin_1',
                                  runScript="")
        s1 = self.app.sessions.start_session(
            dc1, VirtualMachine("session1"))
        response = self.vmmaster_client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        sessions = body['result']['sessions']
        self.assertEqual(1, len(sessions))
        self.assertEqual(self.platform, sessions[0]['platform'])
        self.assertEqual(200, body['metacode'])
        s1.close()

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
        from vmmaster.webdriver.commands import DesiredCapabilities
        dc = DesiredCapabilities(name="session1",
                                 platform='test_origin_1',
                                 runScript="")
        session = self.app.sessions.start_session(
            dc, VirtualMachine("session1"))
        response = self.vmmaster_client.post("/api/session/%s/stop"
                                             % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])
        self.assertEqual(0, len(self.app.sessions.map))

# coding: utf-8

import unittest
import json
from mock import Mock, patch


# Mocking
def session_id(*args, **kwargs):
    from uuid import uuid4

    class Session(object):
        id = uuid4()
    return Session()

from vmmaster.core.virtual_machine import VirtualMachine


class TestApi(unittest.TestCase):
    def shortDescription(self):
        return None  # TODO: move to parent

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
                                      side_effect=session_id))):
            from vmmaster.server import create_app
            self.app = create_app()

        self.client = self.app.test_client()
        self.platforms = self.app.platforms.platforms
        self.platform = self.platforms.keys()[0]
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def tearDown(self):
        with patch('vmmaster.core.db.database', Mock()) as db:
            db.update = Mock()
            self.app.cleanup()
            del self.app

    @patch('vmmaster.core.db.database', Mock())
    def test_api_sessions(self):
        from vmmaster.webdriver.commands import DesiredCapabilities
        dc1 = DesiredCapabilities(name="session1",
                                  platform='test_origin_1',
                                  runScript="")
        s1 = self.app.sessions.start_session(
            dc1, VirtualMachine("session1"))
        dc2 = DesiredCapabilities(name="session2",
                                  platform='test_origin_1',
                                  runScript="")
        s2 = self.app.sessions.start_session(
            dc2, VirtualMachine("session2"))
        response = self.client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        sessions = body['result']['sessions']
        self.assertEqual(2, len(sessions))
        for session in sessions:
            self.assertEqual(self.platform, session['platform'])
        self.assertEqual(200, body['metacode'])
        s1.close()
        s2.close()

    def test_api_platforms(self):
        response = self.client.get('/api/platforms')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        platforms = body['result']['platforms']
        self.assertEqual(2, len(platforms))
        names = [platform for platform in self.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    @patch('vmmaster.core.db.database', Mock())
    def test_api_stop_session(self):
        from vmmaster.webdriver.commands import DesiredCapabilities
        dc = DesiredCapabilities(name="session1",
                                 platform='test_origin_1',
                                 runScript="")
        session = self.app.sessions.start_session(
            dc, VirtualMachine("session1"))
        response = self.client.post("/api/session/%s/stop" % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])
        self.assertEqual(0, len(self.app.sessions.map))

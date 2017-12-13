# coding: utf-8

import os

from flask import Flask
from mock import patch, Mock

from tests.helpers import BaseTestCase, DatabaseMock, wait_for
from core.config import config, setup_config


def run_script_mock(script, host):
    yield 200, {}, '{"output": "test text"}'


def failed_run_script_mock(script, host):
    yield 500, {}, ''


class TestArtifactCollector(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        setup_config('data/config_openstack.py')
        cls.app = Flask(__name__)
        cls.app.database = DatabaseMock()
        cls.app.sessions = Mock()
        cls.session_id = 1
        cls.artifact_dir = os.sep.join([config.SCREENSHOTS_DIR, str(cls.session_id)])
        if not os.path.exists(cls.artifact_dir):
            os.mkdir(cls.artifact_dir)

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('vmpool.artifact_collector.run_script', run_script_mock)
    def test_add_tasks(self):
        """
        - add tasks

        Expected: selenium log was saved and endpoint was deleted
        """
        from vmpool.artifact_collector import ArtifactCollector
        with patch(
            'core.db.Database', DatabaseMock()
        ):
            from core.db.models import Session, Endpoint, Provider
            session = Session('origin_1')
            session.id = self.session_id
            log_path = os.sep.join([self.artifact_dir, 'selenium_server.log'])

            provider = Provider(name='noname', url='nourl')
            endpoint = Endpoint(Mock(), '', provider)
            endpoint.ip = '127.0.0.1'
            endpoint.name = 'test_endpoint'
            endpoint.ports = {'selenium': '4455', 'agent': '9000', 'vnc': '5900'}

            session.endpoint = endpoint
            self.app.sessions.get_session = Mock(return_value=session)

            vmpool = Mock(get_by_name=Mock(return_value=endpoint))
            vmpool.app = self.app
            self.app.pool = vmpool

            art_collector = ArtifactCollector(database=Mock())
            in_queue = art_collector.save_artifact(session, 'selenium_server.log', '/var/log/selenium_server.log')

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))
        with open(log_path, 'r') as f:
            text = f.read()
            self.assertEqual(text, 'test text')

        art_collector.stop()

    @patch('vmpool.artifact_collector.run_script', failed_run_script_mock)
    def test_500_code_run_script_during_add_tasks(self):
        """
        - add tasks

        Expected: selenium log was saved and endpoint was deleted
        """
        from vmpool.artifact_collector import ArtifactCollector
        with patch(
            'core.db.Database', DatabaseMock()
        ):
            from core.db.models import Session, Endpoint, Provider
            session = Session("origin_1")
            session.id = self.session_id

            provider = Provider(name='noname', url='nourl')
            endpoint = Endpoint(Mock(), '', provider)
            endpoint.ip = '127.0.0.1'
            endpoint.name = 'test_endpoint'
            endpoint.ports = {'selenium': '4455', 'agent': '9000', 'vnc': '5900'}

            session.endpoint = endpoint
            art_collector = ArtifactCollector(database=Mock())
            in_queue = art_collector.save_artifact(session, 'selenium_server.log', '/var/log/selenium_server.log')

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))

        art_collector.stop()

    def test_unavailable_run_script_during_add_tasks(self):
        """
        - add tasks

        Expected: selenium log was saved and endpoint was deleted
        """
        from vmpool.artifact_collector import ArtifactCollector
        with patch(
            'core.db.Database', DatabaseMock()
        ):
            from core.db.models import Session, Endpoint, Provider
            session = Session("origin_1")
            session.id = self.session_id
            log_path = os.sep.join([self.artifact_dir, 'selenium_server.log'])

            provider = Provider(name='noname', url='nourl')
            endpoint = Endpoint(Mock(), '', provider)
            endpoint.ip = '127.0.0.1'
            endpoint.name = 'test_endpoint'
            endpoint.ports = {'selenium': '4455', 'agent': '9000', 'vnc': '5900'}

            session.endpoint = endpoint
            self.app.sessions.get_session = Mock(return_value=session)

            art_collector = ArtifactCollector(database=Mock())
            in_queue = art_collector.save_artifact(session, 'selenium_server.log', '/var/log/selenium_server.log')

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))
        with open(log_path, 'r') as f:
            text = f.read()
            self.assertIn('Connection refused', text)

        art_collector.stop()

    def test_stop_artifact_collector(self):
        """
        - stop artifact collector

        Expected: all tasks were deleted
        """
        from vmpool.artifact_collector import ArtifactCollector, Task
        from multiprocessing.pool import AsyncResult

        art_collector = ArtifactCollector(database=Mock())
        task = AsyncResult(cache={1: ""}, callback=None)
        task._job = 1
        task._ready = True
        art_collector.in_queue = {
            1: [Task('my_task', task)]
        }
        art_collector.stop()

        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))

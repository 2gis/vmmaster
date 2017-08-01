# coding: utf-8
import os

from flask import Flask
from mock import patch, Mock
from tests.unit.helpers import BaseTestCase, DatabaseMock, wait_for
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

    @classmethod
    def tearDownClass(cls):
        del cls.app

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
            from core.sessions import Session
            session = Session(dc={'platform': 'origin_1'})
            session.id = 1
            log_path = os.sep.join([config.SCREENSHOTS_DIR, str(session.id), 'selenium_server.log'])
            endpoint = Mock(
                ip='127.0.0.1', name='test_endpoint', delete=Mock(),
                selenium_port=4455, agent_port=9000, vnc_port=5900
            )
            session.endpoint = endpoint
            self.app.database.get_session = Mock(return_value=session)

            vmpool = Mock(get_by_name=Mock(return_value=endpoint))
            vmpool.app = self.app
            self.app.pool = vmpool

            art_collector = ArtifactCollector(vmpool)
            in_queue = art_collector.add_tasks(
                session, {'selenium_server': '/var/log/selenium_server.log'}
            )

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: session.selenium_log == log_path))
        with open(session.selenium_log, 'r') as f:
            text = f.read()
            self.assertEqual(text, 'test text')
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))
        self.assertTrue(wait_for(
            lambda: session.endpoint.delete.called))
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
            from core.sessions import Session
            session = Session(dc={'platform': 'origin_1'})
            session.id = 1
            endpoint = Mock(
                ip='127.0.0.1', name='test_endpoint', delete=Mock(),
                selenium_port=4455, agent_port=9000, vnc_port=5900
            )
            session.endpoint = endpoint
            self.app.database.get_session = Mock(return_value=session)

            vmpool = Mock(get_by_name=Mock(return_value=endpoint))
            vmpool.app = self.app
            self.app.pool = vmpool

            art_collector = ArtifactCollector(vmpool)
            in_queue = art_collector.add_tasks(
                session, {'selenium_server': '/var/log/selenium_server.log'}
            )

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: not session.selenium_log))
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))
        self.assertTrue(wait_for(
            lambda: session.endpoint.delete.called))
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
            from core.sessions import Session
            session = Session(dc={'platform': 'origin_1'})
            session.id = 1
            log_path = os.sep.join([config.SCREENSHOTS_DIR, str(session.id), 'selenium_server.log'])
            endpoint = Mock(
                ip='127.0.0.1', name='test_endpoint', delete=Mock(),
                selenium_port=4455, agent_port=9000, vnc_port=5900
            )
            session.endpoint = endpoint
            self.app.database.get_session = Mock(return_value=session)

            vmpool = Mock(get_by_name=Mock(return_value=endpoint))
            vmpool.app = self.app
            self.app.pool = vmpool

            art_collector = ArtifactCollector(vmpool)
            in_queue = art_collector.add_tasks(
                session, {'selenium_server': '/var/log/selenium_server.log'}
            )

        self.assertTrue(in_queue)
        self.assertTrue(wait_for(
            lambda: session.selenium_log == log_path))
        with open(session.selenium_log, 'r') as f:
            text = f.read()
            self.assertEqual(text, '[Errno -2] Name or service not known')
        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))
        self.assertTrue(wait_for(
            lambda: session.endpoint.delete.called))
        art_collector.stop()

    def test_stop_artifact_collector(self):
        """
        - stop artifact collector

        Expected: all tasks were deleted
        """
        from vmpool.artifact_collector import ArtifactCollector
        from multiprocessing.pool import AsyncResult

        art_collector = ArtifactCollector(Mock())
        task = AsyncResult(cache={1: ""}, callback=None)
        task._job = 1
        task._ready = True
        art_collector.in_queue = {
            1: [task]
        }
        art_collector.stop()

        self.assertTrue(wait_for(
            lambda: len(art_collector.get_queue()) == 0))

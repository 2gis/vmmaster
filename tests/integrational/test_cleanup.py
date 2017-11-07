# coding: utf-8

import os
import unittest
from mock import Mock, patch

from core.utils import system_utils
from core.config import setup_config, config


class TestCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_config('data/config.py')

        from flask import Flask
        cls.app = Flask(__name__)
        cls.app.sessions = None

        from core import db
        cls.app.database = db.Database(config.DATABASE)

        with patch(
            'core.utils.init.home_dir', Mock(return_value=config.BASEDIR)
        ):
            from vmmaster import cleanup
            cls.cleanup = cleanup

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_file_deletion(self):
        from core.db.models import Session
        session = Session('some_platform')
        session.status = 'unknown'
        session.name = '__test_file_deletion'
        session.save()

        session_dir = os.path.join(
            config.SCREENSHOTS_DIR, str(session.id)
        )
        system_utils.run_command(
            ["mkdir", config.SCREENSHOTS_DIR],
            silent=True)
        system_utils.run_command(
            ["mkdir", session_dir],
            silent=True)
        system_utils.run_command(
            ["touch", os.path.join(session_dir, "file_for_deletion")],
            silent=True)
        self.cleanup.delete_session_data([session])
        self.assertEqual(os.path.isdir(session_dir), 0)
        system_utils.run_command(
            ["rm", "-rf", config.SCREENSHOTS_DIR], silent=True)

    def test_sessions_overflow(self):
        user = Mock(id=1, max_stored_sessions=0)
        from core.db.models import Session
        session = Session('some_platform')
        session.status = 'unknown'
        session.closed = True
        session.name = '__test_outdated_sessions'
        session.save()

        session_ids_to_delete = [p.id for p in self.cleanup.sessions_overflow(user)]

        self.assertIn(session.id, session_ids_to_delete)
        self.cleanup.delete_session_data([session])

    def test_session_keep_forever(self):
        user = Mock(id=1, max_stored_sessions=0)

        from core.db.models import Session
        session1 = Session(platform='some_platform', name='__test_keep_forever_sessions_1')
        session1.closed = True
        session1.keep_forever = True
        session1.save()

        session2 = Session(platform='some_platform', name='__test_keep_forever_sessions_2')
        session2.closed = True
        session2.keep_forever = False
        session2.save()

        session_ids_to_delete = [p.id for p in self.cleanup.sessions_overflow(user)]

        self.assertNotIn(session1.id, session_ids_to_delete)
        self.assertIn(session2.id, session_ids_to_delete)

        self.cleanup.delete_session_data([session1, session2])

    def test_endpoints_cleanup(self):
        """
        - endpoint1 linked with session
        - endpoint2 not linked with session
        - both endpoints mark as 'deleted'
        expected: endpoint1 deleted, endpoint2 not deleted
        """
        class FakeOrigin(str):
            short_name = 'fake_short_name'

        from core.db.models import Session, Endpoint, Provider
        provider = Provider('name', 'url')
        endpoint1 = Endpoint(origin=FakeOrigin('fake'), prefix='prefix', provider=provider)
        endpoint2 = Endpoint(origin=FakeOrigin('fake'), prefix='prefix', provider=provider)
        endpoint1.deleted, endpoint2.deleted = True, True
        endpoint1.save(), endpoint2.save()

        session = Session(platform='some_platform', name='__test_keep_forever_sessions_1')
        session.refresh()
        session.endpoint = endpoint1
        session.save()

        endpoints_to_delete = [e.id for e in self.cleanup.endpoints_to_delete()]
        self.assertNotIn(endpoint1.id, endpoints_to_delete)
        self.assertIn(endpoint2.id, endpoints_to_delete)

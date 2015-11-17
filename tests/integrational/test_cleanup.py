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

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()

        with patch(
            'core.utils.init.home_dir', Mock(return_value=config.BASE_DIR)
        ), patch(
            'core.logger.setup_logging', Mock(return_value=Mock())
        ), patch(
            'flask.current_app.sessions', Mock()
        ), patch(
            'core.network.Network', Mock()
        ), patch(
            'core.connection.Virsh', Mock()
        ):
            from vmmaster import cleanup
            self.cleanup = cleanup

            from core.sessions import Session
            self.session = Session()
            self.session.status = 'unknown'

    def tearDown(self):
        self.ctx.pop()

    def test_file_deletion(self):
        self.session.name = '__test_file_deletion'
        self.session.save()

        session_dir = os.path.join(
            config.SCREENSHOTS_DIR, str(self.session.id)
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

        self.cleanup.delete_session_data([self.session])
        self.assertEqual(os.path.isdir(session_dir), 0)
        system_utils.run_command(
            ["rm", "-rf", config.SCREENSHOTS_DIR], silent=True)

    def test_sessions_overflow(self):
        user = Mock(id=1, max_stored_sessions=0)
        self.session.closed = True
        self.session.name = '__test_outdated_sessions'
        self.session.save()

        sessions_to_delete = self.cleanup.sessions_overflow(user)

        session_ids = [s.id for s in sessions_to_delete]

        self.assertIn(self.session.id, session_ids)
        self.cleanup.delete_session_data([self.session])

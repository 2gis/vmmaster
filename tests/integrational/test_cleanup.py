# coding: utf-8

import os
import unittest
from mock import Mock, patch

from core.utils import system_utils
from core.config import setup_config, config


class TestCleanup(unittest.TestCase):
    @classmethod
    def setUp(cls):
        setup_config('data/config.py')

        from core import db
        db.database = db.Database(config.DATABASE)

    def tearDown(self):
        pass

    def test_file_deletion(self):
        with patch('core.utils.init.home_dir',
                Mock(return_value=config.BASE_DIR)), \
            patch('core.logger.setup_logging',
                Mock(return_value=Mock())):
            from vmmaster import cleanup
            from vmmaster.core.sessions import Session

        session = Session()
        session.status = 'unknown'
        session.name = '__test_file_deletion'
        session.save()

        session_dir = os.path.join(config.SCREENSHOTS_DIR, str(session.id))
        system_utils.run_command(
            ["mkdir", config.SCREENSHOTS_DIR],
            silent=True)
        system_utils.run_command(
            ["mkdir", session_dir],
            silent=True)
        system_utils.run_command(
            ["touch", os.path.join(session_dir, "file_for_deletion")],
            silent=True)

        cleanup.delete_session_data([session])
        self.assertEqual(os.path.isdir(session_dir), 0)
        system_utils.run_command(
            ["rm", "-rf", config.SCREENSHOTS_DIR], silent=True)

    def test_outdated_sessions(self):
        with patch('core.utils.init.home_dir',
                   Mock(return_value=config.BASE_DIR)), \
            patch('core.logger.setup_logging',
                  Mock(return_value=Mock())):
        from vmmaster import cleanup
        from time import time
        from vmmaster.core.sessions import Session

        session = Session()
        session.status = 'unknown'
        session.closed = True
        session.name = '__test_outdated_sessions'
        session.time_created = \
            (time() - 60 * 60 * 24 * config.SCREENSHOTS_DAYS - 1)
        session.save()

        outdated_sessions = cleanup.old_sessions()
        outdated_ids = [s.id for s in outdated_sessions]

        self.assertIn(session.id, outdated_ids)
        cleanup.delete_session_data([session])

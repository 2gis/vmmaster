import unittest
import os
from vmmaster import cleanup
from vmmaster.core.utils import system_utils
from vmmaster.core.config import setup_config, config

setup_config('data/config.py')
session_factory = None


class TestCleanup(unittest.TestCase):
    @classmethod
    def setUp(cls):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from vmmaster.core.db import Database
        cls.database = Database(config.DATABASE)

        engine = create_engine(config.DATABASE)
        session_factory = sessionmaker(bind=engine)

    def tearDown(self):
        pass

    def test_file_deletion(self):
        session = self.database.create_session(
            status='unknown',
            name='test_file_deletion'
        )
        session_id = session.id
        session_dir = os.path.join(config.SCREENSHOTS_DIR, str(session_id))

        system_utils.run_command(["mkdir", session_dir])
        system_utils.run_command(["touch", os.path.join(session_dir, "test_file_deletion")])

        cleanup.delete_session_data([session])
        self.assertEqual(os.path.isdir(session_dir), 0)

    def test_outdated_sessions(self):
        from time import time
        session = self.database.create_session(
            status='unknown',
            name='test_file_deletion',
            time=(time() - 60 * 60 * 24 * config.SCREENSHOTS_DAYS - 1)
        )
        is_session_outdated = False
        outdated_sessions = cleanup.old_sessions()
        for outdated_session in outdated_sessions:
            if outdated_session.id == session.id:
                is_session_outdated = True
                break
        self.assertEqual(is_session_outdated, True)
import time
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vmmaster.console.init import home_dir
from vmmaster.core.config import setup_config, config
from vmmaster.core.db import Session, LogStep
from vmmaster.utils.utils import rm, change_user_vmmaster

setup_config('%s/config.py' % home_dir())


def delete_screenshot(log_step):
    if log_step.screenshot:
        os.remove(log_step.screenshot)


def get_screenshots(log_steps):
    screenshots = []
    for log_step in log_steps:
        if log_step.screenshot:
            screenshots += [log_step.screenshot]

    return screenshots


def old():
    d = time.time() - 60 * 60 * 24 * config.SCREENSHOTS_DAYS
    return d


def old_sessions(session):
    return session.query(Session).filter(Session.time < old()).all()


def old_log_steps(session, _old_sessions):
    _old_log_steps = []
    for old_session in _old_sessions:
        _old_log_steps += session.query(LogStep).filter(LogStep.session_id == old_session.id).all()

    return _old_log_steps


def delete_old(session, old_ones):
    for old_one in old_ones:
        session.delete(old_one)


def run():
    change_user_vmmaster()
    engine = create_engine(config.DATABASE)
    session = sessionmaker(bind=engine)()
    try:
        _old_sessions = old_sessions(session)
        _old_log_steps = old_log_steps(session, _old_sessions)
        _screenshots = get_screenshots(_old_log_steps)
        _screenshots = ['/var/lib/vmmaster/screenshots/test1', '/var/lib/vmmaster/screenshots/test2']
        rm(_screenshots)
        old_ones = _old_sessions + _old_log_steps
        delete_old(session, old_ones)
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run()
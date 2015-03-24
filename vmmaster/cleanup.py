import os
import time
import sys
import math
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vmmaster.core.utils.init import home_dir
from vmmaster.core.config import setup_config, config
setup_config('%s/config.py' % home_dir())
from vmmaster.core.db import Session, VmmasterLogStep, SessionLogStep
from vmmaster.core.utils.utils import change_user_vmmaster
from shutil import rmtree

outdated_sessions = None
outdated_vmmaster_logsteps_count = 0
outdated_session_logsteps_count = 0
outdated_screenshots_count = 0


engine = create_engine(config.DATABASE)
session_factory = sessionmaker(bind=engine)

progressbar_width = 78


def write(string):
    sys.stdout.write(string)
    sys.stdout.flush()


def progressbar(fullness):
        # setup toolbar
        sys.stdout.write("[%s]" % (" " * progressbar_width))
        sys.stdout.flush()
        sys.stdout.write("\b" * (progressbar_width + 1)) # return to start of line, after '['

        size = int(math.ceil(fullness / 100. * progressbar_width))
        for i in xrange(size):
            sys.stdout.write("=")
            sys.stdout.flush()

        sys.stdout.write("\r")
        sys.stdout.flush()


def transaction(func):
    def wrapper(*args, **kwargs):
        db_session = session_factory()
        try:
            return func(db_session=db_session, *args, **kwargs)
        except:
            db_session.rollback()
            raise
        finally:
            db_session.close()
    return wrapper


def get_screenshots(log_steps):
    screenshots = []
    for log_step in log_steps:
        if log_step.screenshot:
            screenshots += [log_step.screenshot]
    return screenshots


def get_session_log_steps(session, vmmaster_log_steps):
    ids = [vmmaster_log_step.id for vmmaster_log_step in vmmaster_log_steps]
    return session.query(SessionLogStep).filter(SessionLogStep.vmmaster_log_step_id.in_(ids)).all()


def old():
    d = time.time() - 60 * 60 * 24 * config.SCREENSHOTS_DAYS
    return d


@transaction
def old_sessions(db_session=None):
    return db_session.query(Session).filter(Session.time < old()).all()


@transaction
def delete_session_data(outdated_sessions, db_session=None):
    outdated_sessions_count = len(outdated_sessions)
    write("got %s sessions.\n" % str(outdated_sessions_count))
    write("deleting...\n")
    for num, session in enumerate(outdated_sessions):
        db_session.delete(session)
    db_session.commit()
    write("\n\n")
    write("Total: %s sessions\n" % str(outdated_sessions_count))
    # Now delete files:
    for session in outdated_sessions:
        session_dir = os.path.join(config.SCREENSHOTS_DIR, str(session.id))
        try:
            rmtree(session_dir)
        except OSError:
            print "Unable to delete %s." % str(session_dir)
    write("Done on %s!\n" % str(datetime.datetime.now()))


def run():
    change_user_vmmaster()
    outdated_sessions = old_sessions()
    delete_session_data(outdated_sessions)


if __name__ == "__main__":
    run()
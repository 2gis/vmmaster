import os
import time
import sys
import math

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vmmaster.core.utils.init import home_dir
from vmmaster.core.config import setup_config, config
setup_config('%s/config.py' % home_dir())
from vmmaster.core.db import Session, VmmasterLogStep, SessionLogStep
from vmmaster.core.utils.utils import rm, change_user_vmmaster

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
    session_log_steps = []
    for vmmaster_log_step in vmmaster_log_steps:
        session_log_steps += session.query(SessionLogStep).filter(SessionLogStep.vmmaster_log_step_id == vmmaster_log_step.id).all()

    return session_log_steps


def old():
    d = time.time() - 60 * 60 * 24 * config.SCREENSHOTS_DAYS
    return d


@transaction
def old_sessions(db_session=None):
    return db_session.query(Session).filter(Session.time < old()).all()


@transaction
def delete_session_data(session, db_session=None):
    vmmaster_logsteps = db_session.query(VmmasterLogStep).filter(VmmasterLogStep.session_id == session.id).all()
    global outdated_vmmaster_logsteps_count
    outdated_vmmaster_logsteps_count += len(vmmaster_logsteps)

    session_logsteps = get_session_log_steps(db_session, vmmaster_logsteps)
    global outdated_session_logsteps_count
    outdated_session_logsteps_count += len(session_logsteps)

    screenshots = get_screenshots(vmmaster_logsteps)
    global outdated_screenshots_count
    outdated_screenshots_count += len(screenshots)

    rm(screenshots)
    for logstep in session_logsteps:
        db_session.delete(logstep)
    for logstep in vmmaster_logsteps:
        db_session.delete(logstep)
    db_session.delete(session)
    db_session.commit()
    try:
        os.rmdir(os.path.join(config.SCREENSHOTS_DIR, str(session.id)))
    except OSError:
        pass


def run():
    change_user_vmmaster()

    outdated_sessions = old_sessions()
    outdated_sessions_count = len(outdated_sessions)
    write("got %s sessions.\n" % str(outdated_sessions_count))
    write("deleting...\n")

    for num, session in enumerate(outdated_sessions):
        delete_session_data(session)
        percentage = (num + 1)/float(outdated_sessions_count) * 100
        progressbar(percentage)

    write("\n\n")
    write("Total: %s sessions, %s vmmaster logsteps, %s session logsteps, %s screenshots deleted\n" % (
        outdated_sessions_count, outdated_vmmaster_logsteps_count, outdated_session_logsteps_count, outdated_screenshots_count)
    )
    write("Done!\n")


if __name__ == "__main__":
    run()
# coding: utf-8

import os
import logging
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ArgumentError

from core.config import config, setup_config
from core.db.models import Session, User
from core.utils import change_user_vmmaster
from core.utils.init import home_dir

from shutil import rmtree
from errno import ENOENT

setup_config('%s/config.py' % home_dir())
log = logging.getLogger(__name__)

engine = create_engine(config.DATABASE)
session_factory = sessionmaker(bind=engine)


def transaction(func):
    def wrapper(*args, **kwargs):
        dbsession = session_factory()
        try:
            return func(dbsession=dbsession, *args, **kwargs)
        except:
            dbsession.rollback()
            raise
        finally:
            dbsession.close()
    return wrapper


def delete_files(session_id=None):
    if session_id:
        session_dir = os.path.join(config.SCREENSHOTS_DIR, str(session_id))
        try:
            rmtree(session_dir)
            log.debug("Successful deleted dir %s" % session_dir)
        except OSError as os_error:
            # Ignore 'No such file or directory' error
            if os_error.errno != ENOENT:
                log.info('Unable to delete %s (%s)' %
                         (str(session_dir), os_error.strerror))


@transaction
def delete(session_id, dbsession=None):
    obj_to_delete = dbsession.query(Session).get(session_id)
    dbsession.delete(obj_to_delete)
    dbsession.commit()
    log.debug("Successful deleted session %s from db" % obj_to_delete.id)


def delete_session_data(sessions=None):
    sessions_count = len(sessions)

    log.info("Got %s sessions. " % str(sessions_count))
    if sessions_count:
        checkpoint = datetime.now()
        time_step = timedelta(days=0, seconds=10)

        log.info("Done: %s%% (0 / %d)" % ('0.0'.rjust(5), sessions_count))
        for num, session_id in enumerate(sessions):
            delta = datetime.now() - checkpoint
            if delta > time_step or num == sessions_count - 1:
                percentage = str(
                    round((num + 1)/float(sessions_count) * 100, 1))
                log.info("Done: %s%% (%d / %d)" %
                         (percentage.rjust(5), num + 1, sessions_count))
                checkpoint = datetime.now()
            delete_files(session_id)
            delete(session_id)
        log.info(
            "%s sessions have been deleted.\n" % (str(sessions_count)))
    else:
        log.info("Nothing to delete.\n")


@transaction
def get_users(dbsession=None):
    return dbsession.query(User).all()


@transaction
def sessions_overflow(user, dbsession=None):
    res = []
    current_sessions = dbsession.query(Session).\
        filter_by(user_id=user.id).count()

    if current_sessions > user.max_stored_sessions:
        overflow = current_sessions - user.max_stored_sessions
        try:
            res = dbsession.query(Session).\
                filter_by(user_id=user.id).order_by(Session.id).\
                limit(overflow).all()
            res = [session.id for session in res]
        except ArgumentError:
            log.exception("Error during getting sessions ids from db")

    return res


def run():
    log.info('Running cleanup...')
    change_user_vmmaster()
    sessions = []
    for user in get_users():
        to_delete = sessions_overflow(user)
        if to_delete:
            log.debug(
                "%s sessions found for %s" % (len(to_delete), user.username))
            sessions += to_delete

    delete_session_data(sessions)

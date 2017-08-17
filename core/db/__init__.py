# coding: utf-8

import logging
from sqlalchemy import create_engine, inspect, desc
from sqlalchemy.orm import sessionmaker, scoped_session

from core.db.models import SessionLogStep, User, Platform
from core.utils import to_thread
from core.config import config

log = logging.getLogger(__name__)


def threaded_transaction(func):
    @to_thread
    def wrapper(self, *args, **kwargs):
        dbsession = sessionmaker(bind=self.engine)()
        try:
            return func(self, dbsession=dbsession, *args, **kwargs)
        except:
            dbsession.rollback()
            raise
        finally:
            dbsession.close()
    return wrapper


def transaction(func):
    def wrapper(self, *args, **kwargs):
        # Try to use passed dbsession
        if 'dbsession' in kwargs.keys():
            if kwargs['dbsession'] is not None:
                return func(self, *args, **kwargs)
        dbsession = self.DBSession()
        try:
            return func(self, dbsession=dbsession, *args, **kwargs)
        except:
            dbsession.rollback()
            raise
        finally:
            dbsession.close()
    return wrapper


class Database(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, connection_string=None):
        if not connection_string:
            connection_string = config.DATABASE

        self.engine = create_engine(connection_string,
                                    pool_size=200,
                                    max_overflow=100,
                                    pool_timeout=60)
        self.session_maker = sessionmaker(bind=self.engine,
                                          autocommit=False,
                                          autoflush=False,
                                          expire_on_commit=False)
        self.DBSession = scoped_session(self.session_maker)

    @transaction
    def get_session(self, session_id, dbsession=None):
        if not session_id:
            return None
        from core.sessions import Session
        return dbsession.query(Session).get(session_id)

    @transaction
    def get_log_steps_for_session(self, session_id, dbsession=None):
        return dbsession.query(SessionLogStep).filter_by(
            session_id=session_id).order_by(
                desc(SessionLogStep.id)).all()

    @transaction
    def get_step_by_id(self, log_step_id, dbsession=None):
        return dbsession.query(SessionLogStep).get(log_step_id)

    @transaction
    def get_user(self, username=None, user_id=None, token=None, dbsession=None):
        if user_id:
            return dbsession.query(User).get(user_id)
        elif username:
            return dbsession.query(User).filter_by(username=username).first()
        elif token:
            return dbsession.query(User).filter_by(token=token).first()
        return None

    @transaction
    def get_platform(self, name, dbsession=None):
        return dbsession.query(Platform).filter_by(name=name).first()

    def register_platforms(self, node, platforms):
        for name in platforms:
            try:
                self.add(Platform(name, node))
            except Exception as e:
                log.exception(
                    'Error registering platform: %s (%s)' %
                    (name, e.message)
                )

    @transaction
    def unregister_platforms(self, uuid, dbsession=None):
        dbsession.query(Platform).filter_by(node=uuid).delete()
        dbsession.commit()

    @transaction
    def add(self, obj, dbsession=None):
        dbsession.add(obj)
        dbsession.commit()
        return obj

    @transaction
    def update(self, obj, dbsession=None):
        dbsession.merge(obj)
        dbsession.commit()
        updated_obj = dbsession.query(type(obj)).get(obj.id)
        dbsession.flush()
        return updated_obj

    def refresh(self, obj):
        obj_state = inspect(obj)
        if obj_state.detached:
            dbsession = self.DBSession()
        else:
            dbsession = self.DBSession.object_session(obj)
        return dbsession.add(obj)

    @transaction
    def delete(self, obj, dbsession=None):
        obj_to_delete = dbsession.query(type(obj)).get(obj.id)
        dbsession.delete(obj_to_delete)
        dbsession.commit()
        return obj_to_delete

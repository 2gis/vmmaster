# coding: utf-8

from sqlalchemy import create_engine, inspect, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import SessionLogStep, User, \
    VirtualMachine
from core.utils.utils import to_thread


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

    def __init__(self, connection_string):
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
        from core.sessions import Session as WrappedSession
        return dbsession.query(WrappedSession).get(session_id)

    @transaction
    def get_last_step(self, session, dbsession=None):
        return dbsession.query(SessionLogStep).filter_by(
            session_id=session.id, milestone=True).order_by(
                desc(SessionLogStep.id)).first()

    @transaction
    def get_vm(self, vm_id, dbsession=None):
        return dbsession.query(VirtualMachine).get(vm_id)

    @transaction
    def get_sessions(self, dbsession=None):
        from core.sessions import Session as WrappedSession
        return dbsession.query(WrappedSession).filter_by(
            closed=False, timeouted=False, status='running').all()

    @transaction
    def get_queue(self, dbsession=None):
        from core.sessions import Session as WrappedSession
        return dbsession.query(WrappedSession).filter_by(
            status='waiting').all()

    @transaction
    def get_user(self, username=None, user_id=None, dbsession=None):
        if user_id:
            return dbsession.query(User).get(user_id)
        elif username:
            return dbsession.query(User).filter_by(username=username).first()
        return None

    @transaction
    def complete_session(self, control_line, body=None, session_id=None,
                         dbsession=None):
        step = SessionLogStep(control_line, body, session_id)
        step.save()
        return step

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


database = None

# coding: utf-8


from time import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from .models import Session, VmmasterLogStep, SessionLogStep

from ..utils.utils import to_thread


def threaded_transaction(func):
    @to_thread
    def wrapper(self, *args, **kwargs):
        session = sessionmaker(bind=self.engine)()
        try:
            return func(self, session=session, *args, **kwargs)
        except:
            session.rollback()
            raise
        finally:
            session.close()
    return wrapper


def transaction(func):
    def wrapper(self, *args, **kwargs):
        session = self.Session()
        try:
            return func(self, session=session, *args, **kwargs)
        except:
            session.rollback()
            raise
        finally:
            session.close()
    return wrapper


class Database(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, connection_string):
        self.engine = create_engine(connection_string)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        from vmmaster import migrations
        migrations.run(connection_string)

    @transaction
    def create_session(self, status="running", name=None, time=time(), session=None):
        _session = Session(status=status, time=time)
        session.add(_session)
        session.commit()
        if name is None:
            _session.name = _session.id
        else:
            _session.name = name
        session.add(_session)
        session.commit()
        created_session = session.query(Session).filter_by(id=_session.id).first()
        session.flush()
        return created_session

    @transaction
    def get_session(self, session_id, session=None):
        return session.query(Session).filter_by(id=session_id).first()

    @transaction
    def create_vmmaster_log_step(self, session_id, control_line, body, screenshot="", time=time(), session=None):
        _log_step = VmmasterLogStep(session_id=session_id,
                                    control_line=control_line,
                                    body=body,
                                    screenshot=screenshot,
                                    time=time)
        session.add(_log_step)
        session.commit()
        created_log_step = session.query(VmmasterLogStep).filter_by(id=_log_step.id).first()
        session.flush()
        return created_log_step

    @transaction
    def get_vmmaster_log_step(self, log_step_id, session=None):
        return session.query(VmmasterLogStep).filter_by(id=log_step_id).first()

    @transaction
    def create_session_log_step(self, vmmaster_log_step_id, control_line, body, time=time(), session=None):
        _log_step = SessionLogStep(vmmaster_log_step_id=vmmaster_log_step_id,
                                   control_line=control_line,
                                   body=body,
                                   time=time)
        session.add(_log_step)
        session.commit()
        created_log_step = session.query(SessionLogStep).filter_by(id=_log_step.id).first()
        session.flush()
        return created_log_step

    @transaction
    def get_session_log_step(self, log_step_id, session=None):
        return session.query(SessionLogStep).filter_by(id=log_step_id).first()

    @transaction
    def update(self, obj, session=None):
        session.merge(obj)
        session.commit()
        updated_obj = session.query(type(obj)).filter_by(id=obj.id).first()
        session.flush()
        return updated_obj

database = None
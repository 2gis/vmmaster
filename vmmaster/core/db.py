from time import time

from twisted.internet import threads

from sqlalchemy import create_engine, pool
from sqlalchemy import Column, Integer, Sequence, String, Float, Enum
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

from .config import config


def to_thread(f):
    def wrapper(*args, **kwargs):
        return threads.deferToThread(f, *args, **kwargs)
    return wrapper


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
    Base = declarative_base()

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, connection_string):
        self.engine = create_engine(connection_string)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self.Base.metadata.create_all(self.engine)
        from vmmaster import migrations
        migrations.run(connection_string)

    @transaction
    def createSession(self, status="running", name=None, time=time(), session=None):
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
    def createLogStep(self, session_id, control_line, body, screenshot="", time=time(), session=None):
        _log_step = LogStep(session_id=session_id,
                            control_line=control_line,
                            body=body,
                            screenshot=screenshot,
                            time=time)
        session.add(_log_step)
        session.commit()
        created_log_step = session.query(LogStep).filter_by(id=_log_step.id).first()
        session.flush()
        return created_log_step

    @transaction
    def update(self, obj, session=None):
        session.merge(obj)
        session.commit()
        updated_obj = session.query(type(obj)).filter_by(id=obj.id).first()
        session.flush()
        return updated_obj

    @transaction
    def getSession(self, session_id, session=None):
        return session.query(Session).filter_by(id=session_id).first()

    @transaction
    def getLogStep(self, log_step_id, session=None):
        return session.query(LogStep).filter_by(id=log_step_id).first()


class Session(Database.Base):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'),  primary_key=True)
    status = Column(Enum('unknown', 'running', 'succeed', 'failed'))
    name = Column(String)
    error = Column(String)
    time = Column(Float)


class LogStep(Database.Base):
    __tablename__ = 'log_steps'

    id = Column(Integer, Sequence('log_step_id_seq'),  primary_key=True)
    session_id = Column(Integer)
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    time = Column(Float)


database = Database(config.DATABASE)
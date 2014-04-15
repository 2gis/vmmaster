from time import time

from twisted.internet import threads

from sqlalchemy import create_engine, pool
from sqlalchemy import Column, Integer, Sequence, String, Float
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


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
        session = sessionmaker(bind=self.engine)()
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

    def __init__(self, connection_string, poolclass=pool.SingletonThreadPool):
        self.engine = create_engine(connection_string, poolclass=poolclass)
        self.Base.metadata.create_all(self.engine)

    @transaction
    def createSession(self, name, session=None):
        _session = Session(name=name)
        session.add(_session)
        session.commit()
        db_session = session.query(Session).filter_by(id=_session.id).first()
        session.flush()
        return db_session

    @transaction
    def createLogStep(self, session_id, control_line, headers, screenshot="", time=time(), session=None):
        _log_step = LogStep(session_id=session_id,
                            control_line=control_line,
                            headers=headers,
                            screenshot=screenshot,
                            time=time)
        session.add(_log_step)
        session.commit()
        db_log_step = session.query(LogStep).filter_by(id=_log_step.id).first()
        session.flush()
        return db_log_step

    @transaction
    def update(self, obj, session=None):
        session.add(obj)
        session.commit()


class Session(Database.Base):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'),  primary_key=True)
    name = Column(String)


class LogStep(Database.Base):
    __tablename__ = 'log_steps'

    id = Column(Integer, Sequence('log_step_id_seq'),  primary_key=True)
    session_id = Column(Integer)
    control_line = Column(String)
    headers = Column(String)
    screenshot = Column(String)
    time = Column(Float)
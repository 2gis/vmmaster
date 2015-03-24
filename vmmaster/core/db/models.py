# coding: utf-8

from sqlalchemy import Column, Integer, Sequence, String, Float, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class SessionLogStep(Base):
    __tablename__ = 'session_log_steps'

    id = Column(Integer, Sequence('session_log_steps_id_seq'),  primary_key=True)
    vmmaster_log_step_id = Column(Integer, ForeignKey('vmmaster_log_steps.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    time = Column(Float)


class VmmasterLogStep(Base):
    __tablename__ = 'vmmaster_log_steps'

    id = Column(Integer, Sequence('vmmaster_log_steps_id_seq'),  primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    time = Column(Float)
    agent_steps = relationship(SessionLogStep, backref="vmmaster_log_step", passive_deletes=True)


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'),  primary_key=True)
    status = Column('status', Enum('unknown', 'running', 'succeed', 'failed', name='status', native_enum=False))
    name = Column(String)
    error = Column(String)
    time = Column(Float)
    session_steps = relationship(VmmasterLogStep, backref="session", passive_deletes=True)
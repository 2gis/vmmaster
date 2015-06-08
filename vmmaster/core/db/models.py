# coding: utf-8

import time

from sqlalchemy import Column, Integer, Sequence, String, Float, Enum, \
    ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4


Base = declarative_base()


class SessionLogStep(Base):
    __tablename__ = 'session_log_steps'

    id = Column(Integer,
                Sequence('session_log_steps_id_seq'),
                primary_key=True)
    vmmaster_log_step_id = Column(Integer, ForeignKey('vmmaster_log_steps.id',
                                                      ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    time = Column(Float)


class VmmasterLogStep(Base):
    __tablename__ = 'vmmaster_log_steps'

    id = Column(Integer,
                Sequence('vmmaster_log_steps_id_seq'),
                primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    time = Column(Float)
    agent_steps = relationship(SessionLogStep,
                               backref="vmmaster_log_step",
                               passive_deletes=True)


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete='SET DEFAULT'),
                     nullable=True,
                     default=1)
    vm_id = Column(ForeignKey('virtual_machines.id', ondelete='SET NULL'),
                   nullable=True, default=None)
    status = Column('status', Enum('unknown',
                                   'running',
                                   'succeed',
                                   'failed',
                                   name='status', native_enum=False))
    name = Column(String)
    error = Column(String)
    time = Column(Float)
    session_steps = relationship(VmmasterLogStep,
                                 backref="session",
                                 passive_deletes=True)


class User(Base):
    __tablename__ = 'users'

    def generate_token(self):
        return str(uuid4())

    def regenerate_token(self):
        from vmmaster.core import db
        self.token = self.generate_token()
        db.database.update(self)  # TODO: replace with SAVE()
        return self

    @property
    def info(self):
        return {
            "username": self.username,
        }

    id = Column(Integer, primary_key=True)
    username = Column(String(length=30), unique=True, nullable=False)
    password = Column(String(128))
    allowed_machines = Column(Integer, default=1)
    group_id = Column(ForeignKey('user_groups.id', ondelete='SET DEFAULT'),
                      nullable=True,
                      default=1)
    is_active = Column(Boolean, default=True)
    date_joined = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime)
    token = Column(String(50), nullable=True, default=generate_token)

    sessions = relationship(Session, backref="user", passive_deletes=True)


class UserGroup(Base):
    __tablename__ = 'user_groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(length=20), unique=True, nullable=False)

    users = relationship(User, backref="group", passive_deletes=True)


class VirtualMachine(Base):
    __tablename__ = 'virtual_machines'

    id = Column(Integer, primary_key=True)

    name = Column(String, default=None)
    ip = Column(String, default=None)
    mac = Column(String, default=None)
    platform = Column(String, default=None)

    ready = Column(Boolean, default=False)
    checking = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    created = Column(Float, default=None)

    session = relationship(Session,  uselist=False, backref="vm",
                           enable_typechecks=False)

    def __init__(self, name):
        self.name = name
        self.created = time.time()
        from vmmaster.core.db import database
        database.add(self)

    def save(self):
        """Save object to DB"""
        from vmmaster.core.db import database
        database.update(self)

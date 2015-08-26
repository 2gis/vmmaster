# coding: utf-8

import time
import json
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Sequence, String, Float, Enum, \
    ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship, backref

Base = declarative_base()


class FeaturesMixin(object):
    def add(self):
        from vmmaster.core.db import database
        database.add(self)

    def save(self):
        from vmmaster.core.db import database
        database.update(self)

    def refresh(self):
        from vmmaster.core.db import database
        database.refresh(self)


class SessionLogSubStep(Base, FeaturesMixin):
    __tablename__ = 'sub_steps'

    id = Column(Integer, Sequence('sub_steps_id_seq'), primary_key=True)
    session_log_step_id = Column(Integer, ForeignKey(
        'session_log_steps.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    time_created = Column(Float, default=time.time)

    def __init__(self, control_line, body=None, parent_id=None):
        self.control_line = control_line
        self.body = body
        if parent_id:
            self.session_log_step_id = parent_id
        self.add()


class SessionLogStep(Base, FeaturesMixin):
    __tablename__ = 'session_log_steps'

    id = Column(Integer, Sequence('session_log_steps_id_seq'),
                primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    time_created = Column(Float, default=time.time)
    milestone = Column(Boolean)

    # Relationships
    sub_steps = relationship(
        SessionLogSubStep, backref="session_log_step")

    def __init__(self, control_line, body=None, session_id=None,
                 milestone=True):
        self.control_line = control_line
        self.body = body
        self.milestone = milestone
        if session_id:
            self.session_id = session_id
        self.add()

    def add_sub_step(self, control_line, body):
        return SessionLogSubStep(control_line=control_line,
                                 body=body,
                                 parent_id=self.id)


class Session(Base, FeaturesMixin):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete='SET NULL'), default=1)
    endpoint_id = Column(Integer)
    endpoint_ip = Column(String)
    endpoint_name = Column(String)
    name = Column(String)
    platform = Column(String)
    dc = Column(String)
    selenium_session = Column(String)
    take_screenshot = Column(Boolean)
    run_script = Column(String)
    time_created = Column(Float, default=time.time)
    time_modified = Column(Float, default=time.time)

    # State
    status = Column(Enum('unknown', 'running', 'succeed', 'failed', 'waiting',
                         name='status', native_enum=False), default='waiting')
    error = Column(String)
    timeouted = Column(Boolean, default=False)
    closed = Column(Boolean, default=False)

    # Relationships
    session_steps = relationship(
        SessionLogStep, backref=backref("session", enable_typechecks=False))

    def set_user(self, username):
        from vmmaster.core.db import database
        self.user = database.get_user(username=username)

    def __init__(self, name=None, dc=None):
        if name:
            self.name = name
        else:
            self.name = str(self.id)

        if dc:
            self.dc = json.dumps(dc)
            self.platform = dc["platform"]
            if dc.get("name", None):
                self.name = dc["name"]
            else:
                self.name = str(self.id)

            if dc.get("user", None):
                self.set_user(dc["user"])
            if dc.get("takeScreenshot", None):
                self.take_screenshot = True
            if dc.get("runScript", None):
                self.run_script = json.dumps(dc["runScript"])

        self.add()

    def add_session_step(self, control_line, body=None, milestone=True):
        return SessionLogStep(control_line=control_line,
                              body=body,
                              milestone=milestone,
                              session_id=self.id)

    def get_milestone_step(self):
        """
        Find last session log step marked as milestone for sub_step
        :return: SessionLogStep object
        """
        from vmmaster.core.db import database
        return database.get_last_step(self)


class User(Base, FeaturesMixin):
    __tablename__ = 'users'

    @staticmethod
    def generate_token():
        return str(uuid4())

    def regenerate_token(self):
        self.token = User.generate_token()
        self.save()
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

    # Relationships
    sessions = relationship(Session, backref="user", passive_deletes=True)


class UserGroup(Base):
    __tablename__ = 'user_groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(length=20), unique=True, nullable=False)

    # Relationships
    users = relationship(User, backref="group", passive_deletes=True)


class VirtualMachine(Base, FeaturesMixin):
    __tablename__ = 'virtual_machines'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    ip = Column(String)
    mac = Column(String)
    platform = Column(String)
    time_created = Column(Float, default=time.time)
    time_deleted = Column(Float)

    # State
    ready = Column(Boolean, default=False)
    checking = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    def __init__(self, name, platform):
        self.name = name
        self.platform = platform
        self.add()

    def is_preloaded(self):
        return 'preloaded' in self.name

    @property
    def info(self):
        return {"id": str(self.id),
                "name": str(self.name),
                "ip": str(self.ip),
                "platform": str(self.platform)
        }

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


class AgentLogStep(Base, FeaturesMixin):
    __tablename__ = 'agent_log_steps'

    id = Column(Integer, Sequence('agent_log_steps_id_seq'), primary_key=True)
    session_log_step_id = Column(Integer, ForeignKey(
        'session_log_steps.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    time_created = Column(Float, default=time.time)

    def __init__(self, control_line, body=None):
        self.control_line = control_line
        self.body = body
        self.add()


class SessionLogStep(Base, FeaturesMixin):
    __tablename__ = 'session_log_steps'

    id = Column(Integer,
                Sequence('session_log_steps_id_seq'),
                primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='CASCADE'))
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    time_created = Column(Float, default=time.time)

    # Relationships
    agent_steps = relationship(
        AgentLogStep, backref="session_log_step")

    def __init__(self, control_line, body=None, session_id=None):
        self.control_line = control_line
        self.body = body
        if session_id:
            self.session_id = session_id
        self.add()

    def add_agent_step(self, control_line, body):
        step = AgentLogStep(control_line=control_line, body=body)
        self.refresh()
        self.agent_steps.append(step)
        step.save()
        return step


class Session(Base, FeaturesMixin):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete='SET NULL'), default=1)
    vm_id = Column(ForeignKey('virtual_machines.id', ondelete='SET NULL'))
    name = Column(String)
    platform = Column(String)
    _dc = Column("desired_capabilities", String)
    selenium_session = Column(String)
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

    def __init__(self, dc):
        self.platform = dc.platform
        self.dc = dc
        self._dc = json.dumps(dc.to_json())

        if dc.name:
            self.name = dc.name
        else:
            self.name = str(self.id)

        if dc.user:
            from vmmaster.core.db import database
            self.user = database.get_user(username=dc.user)

        self.add()

    @property
    def desired_capabilities(self):
        try:
            dc = self.dc
        except AttributeError:
            dc = json.loads(self._dc)
            from vmmaster.webdriver.commands import DesiredCapabilities
            self.dc = DesiredCapabilities(
                dc.get('name', None),
                dc.get('platform', None),
                dc.get('takeScreenshot', None),
                dc.get('runScript', dict()),
                dc.get('user', None),
                dc.get('token', None)
            )
            dc = self.dc
        return dc

    @desired_capabilities.setter
    def desired_capabilities(self, dc):
        self._dc = json.dumps(dc.to_json())
        self.dc = dc

    def add_session_step(self, control_line, body=None):
        step = SessionLogStep(control_line=control_line,
                              body=body)
        self.refresh()
        self.session_steps.append(step)
        step.save()
        return step


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

    # State
    ready = Column(Boolean, default=False)
    checking = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    # Relationships
    session = relationship(
        Session, backref=backref("virtual_machine",
                                 single_parent=True,
                                 enable_typechecks=False,
                                 cascade="all, delete-orphan"))

    def __init__(self, name, platform):
        self.name = name
        self.platform = platform
        self.add()

    def is_preloaded(self):
        return 'preloaded' in self.name

    @property
    def info(self):
        return {"id": self.id,
                "name": self.name,
                "ip": self.ip,
                "platform": self.platform
        }
# coding: utf-8

import json
import logging
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Sequence, String, Enum, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship, backref

from flask import current_app

from core import constants
from core.exceptions import RequestTimeoutException, EndpointUnreachableError
from core.utils import network_utils

log = logging.getLogger(__name__)
Base = declarative_base()


class FeaturesMixin(object):
    def add(self):
        current_app.database.add(self)

    def save(self):
        current_app.database.update(self)

    def refresh(self):
        current_app.database.refresh(self)

    def delete(self):
        current_app.database.delete(self)


class SessionLogSubStep(Base, FeaturesMixin):
    __tablename__ = 'sub_steps'

    id = Column(Integer, Sequence('sub_steps_id_seq'), primary_key=True)
    session_log_step_id = Column(
        Integer, ForeignKey(
            'session_log_steps.id', ondelete='CASCADE'),
        index=True
    )
    control_line = Column(String)
    body = Column(String)
    created = Column(DateTime, default=datetime.now)

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
    session_id = Column(
        Integer, ForeignKey('sessions.id', ondelete='CASCADE'), index=True
    )
    control_line = Column(String)
    body = Column(String)
    screenshot = Column(String)
    created = Column(DateTime, default=datetime.now)

    # Relationships
    sub_steps = relationship(
        SessionLogSubStep,
        cascade="all, delete",
        backref=backref(
            "session_log_step",
            enable_typechecks=False,
            single_parent=True
        )
    )

    def __init__(self, control_line, body=None, session_id=None, created=None):
        self.control_line = control_line
        self.body = body
        if session_id:
            self.session_id = session_id
        if created:
            self.created = created
        self.add()

    def add_sub_step(self, control_line, body):
        return SessionLogSubStep(control_line=control_line,
                                 body=body,
                                 parent_id=self.id)


class Session(Base, FeaturesMixin):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete='SET NULL'), default=1)
    endpoint_id = Column(ForeignKey('endpoints.id', ondelete='SET NULL'))
    name = Column(String)
    platform = Column(String)
    dc = Column(String)
    selenium_session = Column(String)
    take_screenshot = Column(Boolean, default=False)
    take_screencast = Column(Boolean, default=False)
    run_script = Column(String)
    created = Column(DateTime, default=datetime.now)
    modified = Column(DateTime, default=datetime.now)
    deleted = Column(DateTime)
    selenium_log = Column(String)

    # State
    status = Column(Enum('unknown', 'running', 'succeed', 'failed', 'waiting',
                         name='status', native_enum=False), default='waiting')
    reason = Column(String)
    error = Column(String)
    timeouted = Column(Boolean, default=False)
    closed = Column(Boolean, default=False)
    keep_forever = Column(Boolean, default=False)

    current_log_step = None
    is_active = True
    endpoint = None

    # Relationships
    session_steps = relationship(
        SessionLogStep,
        cascade="all, delete",
        backref=backref(
            "session",
            enable_typechecks=False,
            single_parent=True
        )
    )

    def __init__(self, platform, name=None, dc=None):
        self.platform = platform

        if name:
            self.name = name

        if dc:
            self.dc = json.dumps(dc)

            if dc.get("name", None) and not self.name:
                self.name = dc["name"]

            if dc.get("user", None):
                self.set_user(dc["user"])

            if dc.get("takeScreenshot", None):
                self.take_screenshot = True

            if dc and dc.get('takeScreencast', None):
                self.take_screencast = True

            if dc.get("runScript", None):
                self.run_script = json.dumps(dc["runScript"])

        self.add()

        if not self.name:
            self.name = "Unnamed session " + str(self.id)
            self.save()

    def __str__(self):
        msg = "Session id={} status={}".format(self.id, self.status)
        if self.endpoint:
            msg += " name={} ip={} ports={}".format(self.endpoint.name, self.endpoint.ip, self.endpoint.ports)
        return msg

    @property
    def inactivity(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def duration(self):
        return (datetime.now() - self.created).total_seconds()

    @property
    def is_waiting(self):
        return self.status == 'waiting'

    @property
    def is_running(self):
        return self.status == 'running'

    @property
    def is_done(self):
        return self.status in ('failed', 'succeed')

    @property
    def is_succeed(self):
        return self.status == 'succeed'

    def add_session_step(self, control_line, body=None, created=None):
        self.current_log_step = SessionLogStep(
            control_line=control_line,
            body=body,
            session_id=self.id,
            created=created
        )
        self.save()
        return self.current_log_step

    @property
    def info(self):
        stat = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "platform": self.platform,
            "duration": self.duration,
            "inactivity": self.inactivity,
        }

        self.refresh()
        if self.endpoint:
            stat["endpoint"] = {
                "ip": self.endpoint.ip,
                "name": self.endpoint.name
            }
        return stat

    def start_timer(self):
        self.modified = datetime.now()
        self.save()
        self.is_active = False

    def stop_timer(self):
        self.is_active = True

    def save_artifacts(self):
        if not self.endpoint.ip:
            return False

        return self.endpoint.save_artifacts(self)

    def wait_for_artifacts(self):
        # FIXME: remove sync wait for task
        current_app.pool.artifact_collector.wait_for_complete(self.id)

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if hasattr(self, "ws"):
            self.ws.close()

        if getattr(self, "endpoint", None):
            log.info("Deleting endpoint {} ({}) for session {}".format(self.endpoint.name, self.endpoint.ip, self.id))
            self.save_artifacts()
            self.wait_for_artifacts()
            self.endpoint.delete(try_to_rebuild=True)

        log.info("Session %s closed. %s" % (self.id, self.reason))

    def succeed(self):
        self.status = "succeed"
        self.close()

    def failed(self, tb=None, reason=None):
        if self.closed:
            log.warn("Session %s already closed with reason %s. "
                     "In this method call was tb='%s' and reason='%s'"
                     % (self.id, self.reason, tb, reason))
            return

        self.status = "failed"
        self.error = tb
        self.close(reason)

    def run(self):
        self.modified = datetime.now()
        self.endpoint.start_recorder(self)
        self.status = "running"
        log.info("Session {} starting on {} ({}).".format(self.id, self.endpoint.name, self.endpoint.ip))
        self.save()

    def timeout(self):
        self.timeouted = True
        self.failed(reason="Session timeout. No activity since %s" % str(self.modified))

    def set_user(self, username):
        self.user = current_app.database.get_user(username=username)

    def add_sub_step(self, control_line, body=None):
        if self.current_log_step:
            return self.current_log_step.add_sub_step(control_line, body)

    def make_request(self, port, request, timeout=constants.REQUEST_TIMEOUT):
        try:
            return network_utils.make_request(self.endpoint.ip, port, request, timeout)
        except RequestTimeoutException as e:
            if not self.endpoint.ping_vm(ports=self.endpoint.bind_ports):
                raise EndpointUnreachableError("Endpoint {} unreachable".format(self.endpoint))
            raise e


class Endpoint(Base, FeaturesMixin):
    __tablename__ = 'endpoints'

    id = Column(Integer, primary_key=True)
    uuid = Column(String)
    provider_id = Column(ForeignKey('providers.id', ondelete='SET NULL'), nullable=False)
    name = Column(String)
    ip = Column(String)
    ports = Column(JSON, default={})
    platform_name = Column(String, nullable=False)

    ready = Column(Boolean, default=False)
    in_use = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    created_time = Column(DateTime, nullable=True)
    used_time = Column(DateTime, nullable=True)
    deleted_time = Column(DateTime, nullable=True)

    # Relationships
    provider = relationship("Provider", backref=backref("endpoints", enable_typechecks=False))

    def __str__(self):
        return "Endpoint {}({})".format(self.name, self.id)

    def __init__(self, name_prefix, platform, provider):
        self.provider = provider
        self.created_time = datetime.now()
        self.platform_name = platform
        self.add()

        if name_prefix:
            self.name = "{}-{}".format(name_prefix, self.id)
        else:
            self.name = "Unnamed endpoint(id={}, platform={})".format(str(self.id), platform)

        self.save()


class User(Base, FeaturesMixin):
    __tablename__ = 'users'

    @staticmethod
    def generate_token():
        return str(uuid4())

    def regenerate_token(self):
        self.token = User.generate_token()
        self.save()
        return self.token

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
    max_stored_sessions = Column(Integer, default=100)

    # Relationships
    sessions = relationship(Session, backref=backref("user", enable_typechecks=False), passive_deletes=True)


class UserGroup(Base):
    __tablename__ = 'user_groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(length=20), unique=True, nullable=False)

    # Relationships
    users = relationship(User, backref=backref("group", enable_typechecks=False), passive_deletes=True)


class Platform(Base):
    __tablename__ = 'platforms'

    id = Column(Integer, primary_key=True)
    provider_id = Column(ForeignKey('providers.id', ondelete='SET NULL'), nullable=False)
    name = Column(String(length=100), nullable=False)

    # Relationships
    provider = relationship("Provider", backref=backref("platforms", enable_typechecks=False))

    def __init__(self, name):
        self.name = name


class Provider(Base, FeaturesMixin):
    __tablename__ = 'providers'

    id = Column(Integer, primary_key=True)
    name = Column(String(length=200), nullable=True)
    url = Column(String, nullable=True)
    active = Column(Boolean, default=False)
    config = Column(JSON, default={})

    def __init__(self, name, url, config=None, active=True):
        self.name = name
        self.url = url
        self.active = active

        if config:
            self.config = config

    @property
    def info(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url
        }

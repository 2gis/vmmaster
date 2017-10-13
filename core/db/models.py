# coding: utf-8

import time
import json
import logging
from functools import partial
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Sequence, String, Enum, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship, backref

from flask import current_app

from core.config import config
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
    status = Column(Enum('unknown', 'running', 'succeed', 'failed', 'waiting', 'preparing',
                         name='status', native_enum=False), default='waiting')
    reason = Column(String)
    error = Column(String)
    screencast_started = Column(Boolean, default=False)
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

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if hasattr(self, "ws"):
            self.ws.close()

        if getattr(self, "endpoint", None) and getattr(self.endpoint, "send_to_service", None):
            self.endpoint.send_to_service()
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

    def set_status(self, status):
        self.status = status
        self.save()

    def set_endpoint_id(self, endpoint_id):
        self.endpoint_id = endpoint_id
        self.save()

    def set_screencast_started(self, value):
        self.screencast_started = value
        self.save()

    def restore_endpoint(self):
        self.endpoint = current_app.pool.get_by_id(self.endpoint_id)

    def restore_current_log_step(self):
        self.current_log_step = current_app.database.get_last_session_step(self.id)

    def restore(self):
        self.restore_endpoint()
        self.restore_current_log_step()

    def run(self):
        self.modified = datetime.now()
        self.status = "running"
        self.save()
        log.info("{} starting...".format(self))

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
    endpoint_type = Column(String(20))

    mode = Column(String, default="default")
    ready = Column(Boolean, default=False)
    in_use = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)

    created_time = Column(DateTime, nullable=True)
    used_time = Column(DateTime, nullable=True)
    deleted_time = Column(DateTime, nullable=True)

    # Relationships
    provider = relationship("Provider", backref=backref("endpoints", enable_typechecks=False))

    # Mapping
    __mapper_args__ = {
        'polymorphic_on': endpoint_type,
        'polymorphic_identity': 'endpoint',
    }

    def __str__(self):
        return "{name}({ip})".format(name=self.name, ip=self.ip)

    def __init__(self, origin, prefix, provider):
        self.origin = origin
        self.provider = provider
        self.created_time = datetime.now()
        self.platform_name = origin.short_name
        self.add()

        name_prefix = "{}-p{}".format(prefix, provider.id)
        if name_prefix:
            self.name = "{}-{}".format(name_prefix, self.id)
        else:
            self.name = "Unnamed endpoint(id={}, platform={})".format(str(self.id), self.platform_name)

        self.save()

    def delete(self, try_to_rebuild=False):
        self.set_in_use(False)
        self.deleted_time = datetime.now()
        self.deleted = True
        self.save()
        log.info("Deleted {}".format(self.name))

    def create(self):
        if self.ready:
            log.info("Creation {} was successful".format(self.name))

    def rebuild(self):
        self.set_in_use(False)
        log.info("Rebuild {} was successful".format(self.name))

    @property
    def bind_ports(self):
        return self.ports.values()

    @property
    def original_ports(self):
        return self.ports.keys()

    @property
    def vnc_port(self):
        return config.VNC_PORT

    @property
    def selenium_port(self):
        return config.SELENIUM_PORT

    @property
    def agent_port(self):
        return config.VMMASTER_AGENT_PORT

    @property
    def agent_ws_url(self):
        return "{}:{}".format(self.ip, self.agent_port)

    def service_mode_on(self):
        self.set_mode("service")

    def service_mode_off(self):
        self.set_mode("default")

    def send_to_service(self):
        self.set_mode("wait for service")

    def set_mode(self, mode):
        self.mode = mode
        self.save()

    def set_ready(self, value):
        self.ready = value
        self.save()

    def set_in_use(self, value):
        # TODO: lazy save in db, remove direct calls for Clone and Session
        if not value:
            self.used_time = datetime.now()
        self.in_use = value
        self.save()

    @property
    def info(self):
        return {
            "id": str(self.id),
            "uuid": str(self.uuid),
            "name": str(self.name),
            "ip": str(self.ip),
            "ports": self.ports,
            "platform": str(self.platform_name),
            "created_time": str(self.created_time) if self.used_time else None,
            "used_time": str(self.used_time) if self.used_time else None,
            "deleted_time": str(self.deleted_time) if self.deleted_time else None,
            "ready": str(self.ready),
            "in_use": str(self.in_use),
            "deleted": str(self.deleted)
        }

    def start_recorder(self, session):
        # FIXME: replace current_pool by direct self.pool usage (blocked by db.models state restore issues)
        return current_app.pool.start_recorder(session)

    def save_artifacts(self, session):
        return current_app.pool.save_artifacts(session)

    def is_preloaded(self):
        return 'preloaded' in self.name

    def ping_vm(self):
        ports = self.bind_ports
        timeout = config.PING_TIMEOUT
        result = [False, False]

        log.info("Starting ping vm {clone}: {ip}:{port}".format(
            clone=self.name, ip=self.ip, port=ports))
        start = time.time()
        _ping = partial(network_utils.ping, self.ip)
        while time.time() - start < timeout:
            result = map(_ping, ports)
            if all(result):
                log.info(
                    "Successful ping for {clone} with {ip}:{ports}".format(
                        clone=self.name, ip=self.ip, ports=ports))
                break
            time.sleep(0.1)

        if not all(result):
            fails = [port for port, res in zip(ports, result) if res is False]
            log.info("Failed ping for {clone} with {ip}:{ports}".format(
                clone=self.name, ip=self.ip, ports=str(fails))
            )
            return False

        return True


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

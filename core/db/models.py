# coding: utf-8

import os
import time
import json
import logging
from functools import partial, wraps
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Sequence, String, Enum, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship, backref

from flask import current_app

from core.config import config
from core import constants
from core.exceptions import CreationException
from core.utils import network_utils, exception_handler, kill_process

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
        self.session_log_step_id = parent_id
        current_app.database_task_queue.append((current_app.database.add, (self,)))


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
        current_app.database_task_queue.append((current_app.database.add, (self,)))

    def add_sub_step_to_step(self, control_line, body):
        SessionLogSubStep(
            control_line=control_line,
            body=body,
            parent_id=self.id
        )


class Session(Base, FeaturesMixin):
    __tablename__ = 'sessions'

    id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
    user_id = Column(ForeignKey('users.id', ondelete='SET NULL'), default=1)
    endpoint_id = Column(ForeignKey('endpoints.id', ondelete='SET NULL'))
    provider_id = Column(ForeignKey('providers.id', ondelete='SET NULL'))
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
    vnc_proxy_port = Column(Integer, default=None)
    vnc_proxy_pid = Column(Integer, default=None)

    # State
    status = Column(Enum('unknown', 'running', 'succeed', 'failed', 'waiting', 'preparing',
                         name='status', native_enum=False), default='waiting')
    reason = Column(String)
    error = Column(String)
    screencast_started = Column(Boolean, default=False)
    timeouted = Column(Boolean, default=False)
    closed = Column(Boolean, default=False)
    keep_forever = Column(Boolean, default=False)

    is_active = True

    # Relationships
    session_steps = relationship(
        SessionLogStep,
        cascade="all, delete",
        lazy='subquery',
        backref=backref(
            "session",
            enable_typechecks=False,
            single_parent=True
        )
    )
    endpoint = relationship(
        "Endpoint",
        enable_typechecks=False, single_parent=True, cascade_backrefs=True, lazy='subquery',
        backref=backref(
            "sessions",
            enable_typechecks=False,
            cascade_backrefs=True
        )
    )

    def __init__(self, platform, name=None, dc=None, provider_id=None):
        self.platform = platform
        self.provider_id = provider_id

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

    @property
    def is_preparing(self):
        return self.status == 'preparing'

    @property
    def current_log_step(self):
        self.refresh()
        return self.session_steps[-1] if self.session_steps else None

    def add_session_step(self, control_line, body=None, created=None):
        SessionLogStep(
            control_line=control_line,
            body=body,
            session_id=self.id,
            created=created
        )

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
        if self.endpoint:
            stat["endpoint"] = {
                "ip": self.endpoint.ip,
                "name": self.endpoint.name
            }
        return stat

    def start_timer(self):
        self.modified = datetime.now()
        self.is_active = False

    def stop_timer(self):
        self.is_active = True

    def stop_vnc_proxy(self):
        if self.vnc_proxy_pid:
            return kill_process(self.vnc_proxy_pid)

    def _close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        if self.stop_vnc_proxy():
            log.info("VNC Proxy was stopped for {}".format(self))

        if hasattr(self, "ws"):
            self.ws.close()

        if getattr(self, "endpoint", None) and getattr(self.endpoint, "send_to_service", None):
            self.endpoint.send_to_service()

        log.info("Session %s closed. %s" % (self.id, self.reason))

    def succeed(self):
        self.status = "succeed"
        self._close(reason="Success")

    def failed(self, tb=None, reason=None):
        if self.closed:
            log.warn("Session %s already closed with reason %s. "
                     "In this method call was tb='%s' and reason='%s'"
                     % (self.id, self.reason, tb, reason))
            return

        self.status = "failed"
        self.error = tb
        self._close(reason)

    def set_status(self, status):
        self.status = status
        self.save()

    def set_endpoint(self, endpoint):
        self.endpoint = endpoint
        self.save()

    def set_screencast_started(self, value):
        self.screencast_started = value
        self.save()

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

    def _add_sub_step(self, control_line, body, context):
        with context():
            _log_step = self.current_log_step
            if _log_step:
                _log_step.add_sub_step_to_step(control_line, body)
            else:
                log.warning('No log steps found for session {}. Skip adding sub step'.format(self))

    def add_sub_step(self, control_line, body=None):
        current_app.database_task_queue.append((self._add_sub_step, (control_line, body, current_app.app_context)))

    def make_request(self, port, request,
                     timeout=getattr(config, "REQUEST_TIMEOUT", constants.REQUEST_TIMEOUT)):
        return network_utils.make_request(self.endpoint.ip, port, request, timeout)


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
    environment_variables = Column(JSON, default={})

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
        return "Endpoint {name}({ip})".format(name=self.name, ip=self.ip)

    def __init__(self, origin, prefix, provider):
        self.name = "{}-p{}-{}".format(prefix, provider.id, str(uuid4())[:8])
        self.origin = origin
        self.provider = provider
        self.created_time = datetime.now()
        self.platform_name = origin.short_name
        self.environment_variables = config.DOCKER_CONTAINER_ENVIRONMENT
        self.add()

    def delete(self, try_to_rebuild=False):
        self.set_in_use(False)
        self.deleted_time = datetime.now()
        self.deleted = True
        self.save()
        log.info("Deleted {}".format(self.name))

    def create(self):
        if self.ready:
            log.info("Creation {} was successful".format(self.name))
        else:
            raise CreationException("Creation {} was failed".format(self.name))

    def rebuild(self):
        self.set_in_use(False)
        log.info("Rebuild {} was successful".format(self.name))

    @property
    def bind_ports(self):
        return self.ports.values()

    def __get_prop_from_config(self, prop, default_prop):
        for platform_type in config.PLATFORMS.values():
            for platform_name, platform_settings in platform_type.items():
                if platform_name == self.platform_name:
                    return platform_settings.get(prop, default_prop)

        return default_prop

    @property
    def artifacts(self):
        return self.__get_prop_from_config("artifacts", config.DEFAULT_ARTIFACTS)

    @property
    def defined_ports_from_config(self):
        return self.__get_prop_from_config("ports", config.DEFAULT_PORTS)

    @property
    def vnc_port(self):
        return self.ports.get("vnc")

    @property
    def selenium_port(self):
        return self.ports.get("selenium")

    @property
    def agent_port(self):
        return self.ports.get("agent")

    @property
    def agent_ws_url(self):
        return "{}:{}".format(self.ip, self.agent_port)

    def service_mode_on(self):
        self.set_mode("service")

    def service_mode_off(self):
        self.set_mode("default")

    def send_to_service(self):
        log.debug("Try to send to service {}".format(self))
        if not self.deleted:
            log.info("Setting 'wait for service' status for endpoint {}".format(self))
            self.set_mode("wait for service")

    def set_mode(self, mode):
        self.mode = mode
        self.save()

    def set_ready(self, value):
        self.ready = value
        self.save()

    def set_in_use(self, value):
        if not value:
            self.used_time = datetime.now()
        self.in_use = value
        self.save()

    def set_env_vars(self, env_vars):
        if not isinstance(env_vars, dict):
            return
        self.environment_variables.update(env_vars)
        self.save()

    @property
    def in_pool(self):
        return self.in_use is False

    @property
    def in_service(self):
        return self.mode == "service"

    @property
    def wait_for_service(self):
        return self.mode == "wait for service"

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

    def is_preloaded(self):
        return 'preloaded' in self.name

    def is_ondemand(self):
        return 'ondemand' in self.name

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


def clone_refresher(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.refresh_endpoint()
        return func(self, *args, **kwargs)
    return wrapper


class OpenstackClone(Endpoint):
    __mapper_args__ = {
        'polymorphic_identity': 'openstack',
    }

    nova_client = None

    def __init__(self, origin, prefix, pool):
        openstack_endpoint_prefix = getattr(config, 'OPENSTACK_ENDPOINT_PREFIX', None)
        if openstack_endpoint_prefix:
            prefix = "{}-{}".format(openstack_endpoint_prefix, prefix)
        super(OpenstackClone, self).__init__(origin, prefix, pool.provider)
        self.nova_client = self._get_nova_client()

    @staticmethod
    def _get_nova_client():
        from core.utils import openstack_utils
        return openstack_utils.nova_client()

    @property
    def network_id(self):
        return getattr(config, "OPENSTACK_NETWORK_ID")

    def refresh_endpoint(self):
        self.refresh()

    @staticmethod
    def set_userdata(file_path):
        if os.path.isfile(file_path):
            try:
                return open(file_path)
            except:
                log.exception("Userdata from %s wasn't applied" % file_path)

    @clone_refresher
    def create(self):
        log.info(
            "Creating openstack clone of {} with image={}, "
            "flavor={}".format(self.name, self.image, self.flavor))

        self.ports = self.defined_ports_from_config
        self.save()
        kwargs = {
            'name': self.name,
            'image': self.image,
            'flavor': self.flavor,
            'nics': [{'net-id': self.network_id}],
            'meta': getattr(config, "OPENASTACK_VM_META_DATA", {}),
            'userdata': self.set_userdata(
                getattr(config, "OPENSTACK_VM_USERDATA_FILE_PATH", "userdata")
            )
        }
        if bool(config.OPENSTACK_ZONE_FOR_VM_CREATE):
            kwargs.update({'availability_zone': config.OPENSTACK_ZONE_FOR_VM_CREATE})

        self.nova_client.servers.create(**kwargs)
        self._wait_for_activated_service()
        super(OpenstackClone, self).create()

        # TODO: fill self.uuid with openstack node id (or rename or remove)

    def _parse_ip_from_networks(self):
        server = self.get_vm(self.name)
        if not server:
            return

        addresses = server.networks.get(config.OPENSTACK_NETWORK_NAME, None)
        if addresses is not None:
            ip = addresses[0]
            return ip
        return None

    def get_ip(self):
        try:
            ip = self._parse_ip_from_networks()
            if ip is not None:
                return ip

            log.info(
                "Created openstack {clone} with ip {ip}".format(
                    clone=self.name, ip=ip)
            )

        except Exception as e:
            log.exception("Vm %s does not have address block. Error: %s" %
                          (self.name, e.message))

    def _wait_for_activated_service(self):
        config_create_check_retry_count, config_create_check_pause = \
            config.VM_CREATE_CHECK_ATTEMPTS, config.VM_CREATE_CHECK_PAUSE
        create_check_retry = 1
        ping_retry = 1

        while not self.ready and not self.deleted:
            self.refresh_endpoint()
            server = self.get_vm(self.name)
            if not server:
                log.error("VM %s has not been created." % self.name)
                self.delete()
                break

            if self.is_spawning(server):
                log.info("Virtual Machine %s is spawning..." % self.name)

                if create_check_retry > config_create_check_retry_count:
                    p = config_create_check_retry_count * \
                        config_create_check_pause
                    log.info("VM %s creates more than %s seconds, "
                             "check this VM" % (self.name, p))

                create_check_retry += 1
                time.sleep(config_create_check_pause)

            elif self.is_created(server):
                if not self.ip:
                    self.ip = self.get_ip()
                    self.save()
                if self.ping_vm():
                    self.set_ready(True)
                    break
                if ping_retry > config.VM_PING_RETRY_COUNT:
                    p = config.VM_PING_RETRY_COUNT * config.PING_TIMEOUT
                    log.info("VM {} pings more than {} seconds. Running delete/rebuild".format(self.name, p))
                    self.delete(try_to_rebuild=True)
                    break
                ping_retry += 1

            elif self.is_broken(server):
                log.error("VM %s was errored. Rebuilding..." % server.name)
                self.rebuild()
                break
            else:
                log.warning("Something ugly happened {}".format(server.name))
                break
        else:
            log.debug("VM {} is deleted: stop threaded wait".format(self.name))
        return self.ready

    @property
    def image(self):
        return self.nova_client.glance.find_image(
            "{}{}".format(config.OPENSTACK_PLATFORM_NAME_PREFIX, self.platform_name)
        )

    @property
    def flavor(self):
        return self.nova_client.flavors.find(name=self.origin.flavor_name)

    @staticmethod
    def is_created(server):
        if server.status.lower() == 'active':
            if getattr(server, 'addresses', None) is not None:
                return True

        return False

    @staticmethod
    def is_spawning(server):
        return server.status.lower() in ('build', 'rebuild')

    @staticmethod
    def is_broken(server):
        return server.status.lower() == 'error'

    def get_vm(self, server_name):
        if not self.nova_client:
            self.nova_client = self._get_nova_client()

        try:
            server = self.nova_client.servers.find(name=server_name)
            return server if server else None
        except:
            log.exception("Openstack clone %s does not exist" % server_name)
            return None

    @clone_refresher
    def delete(self, try_to_rebuild=False):
        if try_to_rebuild and self.is_preloaded():
            return self.rebuild()
        else:
            self.set_ready(False)
            server = self.get_vm(self.name)
            try:
                if server:
                    server.delete()
            except:
                log.exception("Delete vm %s was FAILED." % self.name)
            finally:
                super(OpenstackClone, self).delete()
            return self.deleted

    @clone_refresher
    def rebuild(self):
        log.info("Rebuilding openstack {clone}".format(clone=self.name))
        self.set_ready(False)

        server = self.get_vm(self.name)

        try:
            if server:
                server.rebuild(self.image)
                self._wait_for_activated_service()
        except:
            log.exception("Rebuild vm %s was FAILED." % self.name)
            return self.delete()
        finally:
            super(OpenstackClone, self).rebuild()
        return self.ready


class DockerClone(Endpoint):
    __mapper_args__ = {
        'polymorphic_identity': 'docker',
    }

    client = None
    __container = None

    def __init__(self, origin, prefix, pool):
        self.pool = pool
        super(DockerClone, self).__init__(origin, prefix, pool.provider)
        self.client = self._get_client()

    @staticmethod
    def _get_client():
        from core.clients.docker_client import DockerManageClient
        return DockerManageClient()

    def __str__(self):
        return self.name

    def refresh_endpoint(self):
        self.refresh()
        __container = self.get_container()
        if __container:
            self.__container = __container
            self.ports = self.__make_binded_ports()
            self.save()

    @exception_handler(return_on_exc=None)
    def get_container(self):
        if not self.client:
            self.client = self._get_client()

        if self.__container:
            return self.client.get_container(self.__container.id)
        elif self.uuid:
            return self.client.get_container(self.uuid)

    def connect_network(self):
        if self.__container:
            self.pool.network.connect_container(self.__container.id)

    @exception_handler()
    def disconnect_network(self):
        self.refresh_endpoint()
        if self.__container:
            self.pool.network.disconnect_container(self.__container.id)

    @property
    def status(self):
        self.refresh_endpoint()
        if self.__container:
            return self.__container.status.lower()

    @property
    def is_spawning(self):
        return self.status in ('restarting', 'removing')

    @property
    def is_created(self):
        return self.status in ('created', 'running')

    @property
    def is_broken(self):
        return self.status in ('paused', 'exited', 'dead')

    @property
    def image(self):
        return "{}{}".format(config.DOCKER_IMAGE_NAME_PREFIX, self.platform_name)

    def __make_binded_ports(self):
        if not self.__container or not self.__container.ports:
            return {}

        _ports = {}
        for defined_port_name, defined_port in self.defined_ports_from_config.items():
            if defined_port in self.__container.ports:
                _ports[defined_port_name] = self.__container.ports.get(defined_port)

        return _ports

    @clone_refresher
    def create(self):
        kwargs = {
            "image": self.image,
            "name": self.name,
            "env_vars": self.environment_variables
        }

        if config.BIND_LOCALHOST_PORTS:
            kwargs["ports"] = self.defined_ports_from_config.values()

        self.__container = self.client.run_container(**kwargs)

        if config.BIND_LOCALHOST_PORTS:
            self.ports = self.__make_binded_ports()
        else:
            self.ports = self.defined_ports_from_config
            self.connect_network()

        self.uuid = self.__container.id
        self.save()

        log.info("Preparing {}...".format(self.name))
        self._wait_for_activated_service()
        super(DockerClone, self).create()

    @property
    def selenium_is_ready(self):
        for status, headers, body in network_utils.make_request(
            self.ip,
            self.selenium_port,
            network_utils.RequestHelper("GET", "/wd/hub/status"),
            timeout=constants.REQUEST_TIMEOUT_ON_CREATE_ENDPOINT
        ):
            pass
        return status == 200

    def _wait_for_activated_service(self):
        ping_retry = 1

        while not self.ready and not self.deleted:
            self.refresh_endpoint()
            if self.is_spawning:
                log.info("Container {} is spawning...".format(self.name))

            elif self.is_created:
                if not self.__container.ip:
                    log.info("Waiting ip for {}".format(self.name))
                    continue
                self.ip = self.__container.ip
                if self.ping_vm() and self.selenium_is_ready:
                    self.set_ready(True)
                    break
                if ping_retry > config.VM_PING_RETRY_COUNT:
                    p = config.VM_PING_RETRY_COUNT * config.PING_TIMEOUT
                    log.info("Container {} pings more than {} seconds...".format(self.name, p))
                    self.delete(try_to_rebuild=True)
                    break
                ping_retry += 1

            elif self.is_broken or not self.status:
                raise CreationException("Container {} has not been created.".format(self.name))
            else:
                log.warning("Unknown status {} for container {}".format(self.status, self.name))
        return self.ready

    @clone_refresher
    def delete(self, try_to_rebuild=False):
        if try_to_rebuild and self.is_preloaded():
            return self.rebuild()
        else:
            self.set_ready(False)
            try:
                if self.__container:
                    if not config.BIND_LOCALHOST_PORTS:
                        self.disconnect_network()
                    self.__container.stop()
                    self.__container.remove()
                    log.info("Delete {} was successful".format(self.name))
            except:
                log.exception("Delete {} was failed".format(self.name))
            finally:
                super(DockerClone, self).delete()
            return self.deleted

    @clone_refresher
    def rebuild(self):
        log.info("Rebuilding container {}".format(self.name))
        self.set_ready(False)

        try:
            if self.__container:
                self.__container.restart()
                self._wait_for_activated_service()
        except:
            log.exception("Rebuild {} was failed".format(self.name))
            return self.delete()
        finally:
            super(DockerClone, self).rebuild()
        return self.ready


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
    max_limit = Column(Integer, default=0)

    def __init__(self, name, url, config=None, active=True, max_limit=0):
        self.name = name
        self.url = url
        self.active = active
        self.max_limit = max_limit

        if config:
            self.config = config

    @property
    def info(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url
        }

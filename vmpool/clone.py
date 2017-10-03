# coding: utf-8
import os
import time
import logging

from functools import wraps
from functools import partial
from flask import current_app

from core.db import models
from datetime import datetime

from core.exceptions import CreationException
from core.config import config
from core.utils import network_utils, exception_handler


log = logging.getLogger(__name__)


def clone_watcher(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.refresh()
        for value in func(self, *args, **kwargs):
            time.sleep(0.1)
        return value
    return wrapper


class Clone(models.Endpoint):
    def __init__(self, origin, prefix, pool):
        self.origin = origin
        self.pool = pool
        super(Clone, self).__init__(name=self.name, platform=origin.short_name, provider_id=pool.id)
        self.prefix = prefix
        self.name = "p{}-{}-{}".format(pool.id, self.prefix, self.id)
        self.save()

    def __str__(self):
        return "{name}({ip})".format(name=self.name, ip=self.ip)

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

    def ping_vm(self, ports=config.PORTS):
        result = [False, False]
        timeout = config.PING_TIMEOUT
        start = time.time()

        log.info("Starting ping vm {clone}: {ip}:{port}".format(
            clone=self.name, ip=self.ip, port=ports))
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


class OpenstackClone(Clone):
    nova_client = None

    def __init__(self, origin, prefix, pool):
        super(OpenstackClone, self).__init__(origin, prefix, pool)
        openstack_endpoint_prefix = getattr(config, 'OPENSTACK_ENDPOINT_PREFIX', None)
        if openstack_endpoint_prefix:
            self.name = "{}-{}".format(openstack_endpoint_prefix, self.name)
            self.save()
        self.nova_client = self._get_nova_client()
        self.ports = {"{}".format(port): port for port in config.PORTS}
        self.save()

    @staticmethod
    def _get_nova_client():
        from core.utils import openstack_utils
        return openstack_utils.nova_client()

    @property
    def network_id(self):
        return getattr(config, "OPENSTACK_NETWORK_ID")

    @staticmethod
    def set_userdata(file_path):
        if os.path.isfile(file_path):
            try:
                return open(file_path)
            except:
                log.exception("Userdata from %s wasn't applied" % file_path)

    @clone_watcher
    def create(self):
        log.info(
            "Creating openstack clone of {} with image={}, "
            "flavor={}".format(self.name, self.image, self.flavor))

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
        for ready in self._wait_for_activated_service():
            yield ready
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
            yield self.ready
            self.refresh()
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
        yield self.ready

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

    @clone_watcher
    def delete(self, try_to_rebuild=False):
        if try_to_rebuild and self.is_preloaded():
            yield self.rebuild()
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
            yield self.deleted

    @clone_watcher
    def rebuild(self):
        log.info("Rebuilding openstack {clone}".format(clone=self.name))
        self.set_ready(False)

        server = self.get_vm(self.name)

        try:
            if server:
                server.rebuild(self.image)
                for ready in self._wait_for_activated_service():
                    yield ready
        except:
            log.exception("Rebuild vm %s was FAILED." % self.name)
            yield self.delete()
        finally:
            super(OpenstackClone, self).rebuild()
        yield self.ready


class DockerClone(Clone):
    client = None
    __container = None

    def __init__(self, origin, prefix, pool):
        super(DockerClone, self).__init__(origin, prefix, pool)
        self.platform_name = origin.name
        self.client = self._get_client()

    @staticmethod
    def _get_client():
        from core.clients.docker_client import DockerManageClient
        return DockerManageClient()

    def __str__(self):
        return self.name

    @property
    def vnc_port(self):
        return self.ports.get(str(config.VNC_PORT))

    @property
    def selenium_port(self):
        return self.ports.get(str(config.SELENIUM_PORT))

    @property
    def agent_port(self):
        return self.ports.get(str(config.VMMASTER_AGENT_PORT))

    def refresh(self):
        super(DockerClone, self).refresh()
        __container = self.get_container()
        if __container:
            self.__container = __container

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
        self.refresh()
        if self.__container:
            self.pool.network.disconnect_container(self.__container.id)

    @property
    def status(self):
        self.refresh()
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

    @clone_watcher
    def create(self):
        self.__container = self.client.run_container(image=self.platform_name, name=self.name)
        self.refresh()
        self.ports = self.__container.ports
        self.uuid = self.__container.id
        self.save()
        if not config.BIND_LOCALHOST_PORTS:
            self.pool.network.connect_container(self.__container.id)

        log.info("Preparing {}...".format(self.name))
        for ready in self._wait_for_activated_service():
            yield ready
        super(DockerClone, self).create()

    @property
    def selenium_is_ready(self):
        for status, headers, body in network_utils.make_request(
            self.ip,
            self.selenium_port,
            network_utils.RequestHelper("GET", "/wd/hub/status")
        ):
            pass
        return status == 200

    def _wait_for_activated_service(self):
        ping_retry = 1

        while not self.ready and not self.deleted:
            yield self.ready
            self.refresh()
            if self.is_spawning:
                log.info("Container {} is spawning...".format(self.name))

            elif self.is_created:
                if not self.__container.ip:
                    log.info("Waiting ip for {}".format(self.name))
                    continue
                self.ip = self.__container.ip
                if self.ping_vm(ports=self.bind_ports) and self.selenium_is_ready:
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
        yield self.ready

    @clone_watcher
    def delete(self, try_to_rebuild=False):
        if try_to_rebuild and self.is_preloaded():
            yield self.rebuild()
        else:
            self.set_ready(False)
            try:
                if self.__container:
                    if not config.BIND_LOCALHOST_PORTS:
                        self.pool.network.disconnect_container(self.__container.id)
                    self.__container.stop()
                    self.__container.remove()
                    log.info("Delete {} was successful".format(self.name))
            except:
                log.exception("Delete {} was failed".format(self.name))
            finally:
                super(DockerClone, self).delete()
            yield self.deleted

    @clone_watcher
    def rebuild(self):
        log.info("Rebuilding container {}".format(self.name))
        self.set_ready(False)

        try:
            if self.__container:
                self.__container.restart()
                for ready in self._wait_for_activated_service():
                    yield ready
        except:
            log.exception("Rebuild {} was failed".format(self.name))
            yield self.delete()
        finally:
            super(DockerClone, self).rebuild()
        yield self.ready

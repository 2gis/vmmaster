# coding: utf-8

import time
import netifaces
import SubnetTree
import logging

from functools import wraps
from functools import partial
from uuid import uuid4
from threading import Thread

from vmpool import VirtualMachine

from core.exceptions import CreationException
from core.config import config
from core.utils import network_utils, openstack_utils

log = logging.getLogger(__name__)


def threaded_wait(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        def thread_target():
            with self.pool.app.app_context():
                return func(self, *args, **kwargs)

        tr = Thread(target=thread_target)
        tr.daemon = True
        tr.start()

    return wrapper


class Clone(VirtualMachine):
    def __init__(self, origin, prefix, pool):
        self.uuid = str(uuid4())[:8]
        self.prefix = '%s' % prefix
        self.origin = origin
        self.pool = pool
        name = "p{provider_id}-{prefix}-{uuid}".format(
            provider_id=pool.app.id, prefix=self.prefix, uuid=self.uuid)

        super(Clone, self).__init__(name=name, platform=origin.name, provider_id=pool.app.id)

    def __str__(self):
        return "{name}({ip})".format(name=self.name, ip=self.ip)

    def delete(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def rebuild(self):
        raise NotImplementedError

    def save_artifacts(self, session, artifacts):
        return self.pool.save_artifact(session.id, artifacts)

    def ping_vm(self):
        ports = [config.SELENIUM_PORT, config.VMMASTER_AGENT_PORT]
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
    nova_client = openstack_utils.nova_client()
    network_client = openstack_utils.neutron_client()
    network_id = None
    network_name = None

    def __init__(self, origin, prefix, pool):
        super(OpenstackClone, self).__init__(origin, prefix, pool)
        self.platform = origin.short_name
        self.save()

    def create(self):
        self.network_id = self.get_network_id()
        self.network_name = self.get_network_name(self.network_id)
        log.info(
            "Creating openstack clone of {} with image={}, "
            "flavor={}".format(self.name, self.image, self.flavor))

        kwargs = {
            'name': self.name,
            'image': self.image,
            'flavor': self.flavor,
            'nics': [{'net-id': self.network_id}],
            'meta': config.OPENASTACK_VM_META_DATA
        }

        if bool(config.OPENSTACK_ZONE_FOR_VM_CREATE):
            kwargs.update({'availability_zone':
                           config.OPENSTACK_ZONE_FOR_VM_CREATE})

        self.nova_client.servers.create(**kwargs)
        self._wait_for_activated_service(self.get_ip)

    def get_ip(self):
        if self.ip is None:
            try:
                addresses = self.nova_client.servers.find(
                    name=self.name).addresses.get(self.network_name, None)
                if addresses is not None:
                    ip = addresses[0].get('addr', None)
                    self.mac = addresses[0].get('OS-EXT-IPS-MAC:mac_addr',
                                                None)

                    if ip is not None:
                        self.ip = ip

                    log.info(
                        "Created openstack {clone} with ip {ip}"
                        " and mac {mac}".format(
                            clone=self.name, ip=self.ip, mac=self.mac)
                    )
            except Exception as e:
                log.exception("Vm %s does not have address block. Error: %s" %
                              (self.name, e.message))

    @threaded_wait
    def _wait_for_activated_service(self, method=None):
        config_create_check_retry_count, config_create_check_pause = \
            config.VM_CREATE_CHECK_ATTEMPTS, config.VM_CREATE_CHECK_PAUSE
        config_ping_retry_count, config_ping_timeout = \
            config.OPENSTACK_PING_RETRY_COUNT, config.PING_TIMEOUT

        create_check_retry = 1
        ping_retry = 1

        while True:
            try:
                server = self.nova_client.servers.find(name=self.name)
            except Exception as e:
                log.exception(
                    "Can't find vm %s in openstack. Error: %s" %
                    (self.name, e.message)
                )
                server = None

            if server is not None and server.status.lower() in \
                    ('build', 'rebuild'):
                log.info("Virtual Machine %s is spawning..." % self.name)

                if create_check_retry > config_create_check_retry_count:
                    p = config_create_check_retry_count * \
                        config_create_check_pause
                    log.info("VM %s creates more than %s seconds, "
                             "check this VM" % (self.name, p))

                create_check_retry += 1
                time.sleep(config_create_check_pause)

            elif self.vm_has_created():
                if method is not None:
                    method()
                if self.ping_vm():
                    self.ready = True
                    self.save()
                    break
                if ping_retry > config_ping_retry_count:
                    p = config_ping_retry_count * config_ping_timeout
                    log.info("VM %s pings more than %s seconds..." % (self.name, p))
                    self.rebuild()
                    break

                ping_retry += 1
            else:
                log.exception("VM %s has not been created." % self.name)
                self.delete()
                break

    @property
    def image(self):
        return self.nova_client.images.find(name=self.origin.name)

    @property
    def flavor(self):
        return self.nova_client.flavors.find(name=self.origin.flavor_name)

    def get_network_name(self, network_id):
        if network_id:
            for net in self.network_client.list_networks().get('networks', []):
                if net['id'] == network_id:
                    return net['name']
        else:
            raise CreationException('Can\'t return network name because '
                                    'network_id was %s' % str(network_id))

    def get_network_id(self):
        try:
            self_ip = netifaces.ifaddresses('eth0').get(
                netifaces.AF_INET, [{'addr': None}])[0]['addr']
        except ValueError:
            self_ip = None

        if self_ip:
            stree = SubnetTree.SubnetTree()
            for subnet in self.network_client.list_subnets().get(
                    'subnets', []):
                if subnet['tenant_id'] == config.OPENSTACK_TENANT_ID:
                    stree[str(subnet['cidr'])] = str(subnet['network_id'])
                    log.info(
                        "Associate vm with network id %s and subnet id %s"
                        % (str(subnet['network_id']), str(subnet['id'])))

            try:
                net_id = stree[self_ip]
                log.info(
                    "Current network id for creating vm: %s" % net_id)
                return net_id
            except KeyError:
                log.warn("Error: Network id not found in your project.")
                return None
        else:
            log.warn("Error: Your server does not have ip address.")
            return None
            # fixme
            # create new network

    def vm_has_created(self):
        try:
            server = self.nova_client.servers.find(name=self.name)
        except:
            log.exception(
                "An error occurred during addition ip for vm %s" % self.name)
            server = None

        if server is not None:
            if server.status.lower() == 'active':
                if getattr(server, 'addresses', None) is not None:
                    return True

        return False

    def check_vm_exist(self, server_name):
        try:
            server = self.nova_client.servers.find(name=server_name)
            return True if server.name == server_name else False
        except:
            log.exception("VM does not exist.")
            return False

    def delete(self, try_to_rebuild=True):
        if try_to_rebuild and self.is_preloaded():
            self.rebuild()
            return

        self.ready = False
        self.save()
        if self.check_vm_exist(self.name):
            try:
                self.nova_client.servers.find(name=self.name).delete()
            except:
                log.exception("Delete vm %s was FAILED." % self.name)
            log.info("Deleted openstack clone: {clone}".format(
                clone=self.name))
        else:
            log.warn("VM {clone} can not be removed because "
                     "it does not exist".format(clone=self.name))
        VirtualMachine.delete(self)

    def rebuild(self):
        log.info("Rebuilding openstack {clone}".format(clone=self.name))
        self.ready = False
        self.save()
        try:
            self.nova_client.servers.find(name=self.name).rebuild(self.image)
            self._wait_for_activated_service(lambda: log.info(
                "Rebuilded openstack clone: {clone}".format(clone=self.name)))
        except:
            log.exception(
                "Rebuild vm %s was FAILED." % self.name
            )
            self.delete(try_to_rebuild=False)

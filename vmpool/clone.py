# coding: utf-8

import time
import netifaces
import SubnetTree

from functools import wraps
from functools import partial
from xml.dom import minidom
from uuid import uuid4
from threading import Thread

from vmpool import VirtualMachine

from core import dumpxml
from core.logger import log_pool
from core import utils
from core.exceptions import libvirtError, CreationException
from core.config import config
from core.utils import network_utils


def threaded_wait(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        def thread_target():
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
        name = "{platform}-clone-{prefix}-{uuid}".format(
            platform=origin.name, prefix=self.prefix, uuid=self.uuid)

        super(Clone, self).__init__(name=name, platform=origin.name)

    def __str__(self):
        return "{name}({ip})".format(name=self.name, ip=self.ip)

    def delete(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def rebuild(self):
        raise NotImplementedError

    def ping_vm(self):
        ports = [config.SELENIUM_PORT, config.VMMASTER_AGENT_PORT]
        result = [False, False]
        timeout = config.PING_TIMEOUT
        start = time.time()

        log_pool.info("Starting ping vm {clone}: {ip}:{port}".format(
            clone=self.name, ip=self.ip, port=ports))
        _ping = partial(network_utils.ping, self.ip)
        while time.time() - start < timeout:
            result = map(_ping, ports)
            if all(result):
                log_pool.info(
                    "Successful ping for {clone} with {ip}:{ports}".format(
                        clone=self.name, ip=self.ip, ports=ports))
                break
            time.sleep(0.1)

        if not all(result):
            fails = [port for port, res in zip(ports, result) if res is False]
            log_pool.info("Failed ping for {clone} with {ip}:{ports}".format(
                clone=self.name, ip=self.ip, ports=str(fails))
            )
            return False

        return True


class KVMClone(Clone):
    dumpxml_file = None
    drive_path = None

    def __init__(self, origin, prefix, pool):
        super(KVMClone, self).__init__(origin, prefix, pool)

        self.network = self.pool.network
        self.conn = self.network.conn

    def delete(self, try_to_rebuild=True):
        if try_to_rebuild and self.is_preloaded():
            self.rebuild()
            return

        log_pool.info("Deleting kvm clone: {}".format(self.name))
        self.ready = False
        utils.delete_file(self.drive_path)
        utils.delete_file(self.dumpxml_file)
        try:
            domain = self.conn.lookupByName(self.name)
            if domain.isActive():
                domain.destroy()
            domain.undefine()
        except libvirtError:
            # not running
            pass
        try:
            self.network.append_free_mac(self.mac)
        except ValueError, e:
            log_pool.warning(e)
            pass
        self.pool.remove_vm(self)
        VirtualMachine.delete(self)

    def create(self):
        log_pool.info("Creating kvm clone of {platform}".format(
            platform=self.platform)
        )
        self.dumpxml_file = self.clone_origin(self.platform)
        self.define_clone(self.dumpxml_file)
        self.start_virtual_machine(self.name)
        self.ip = self.network.get_ip(self.mac)
        self.ready = True
        log_pool.info("Created kvm {clone} on ip: {ip} with mac: {mac}".format(
            clone=self.name, ip=self.ip, mac=self.mac)
        )
        return self

    def rebuild(self):
        log_pool.info(
            "Rebuilding kvm clone {clone} ({ip}, {platform})...".format(
                clone=self.name, ip=self.ip, platform=self.platform)
        )
        self.pool.remove_vm(self)
        self.delete(try_to_rebuild=False)

        try:
            self.pool.add(
                self.platform, self.prefix, self.pool.pool)
        except CreationException:
            pass

    def clone_origin(self, origin_name):
        self.drive_path = utils.clone_qcow2_drive(origin_name, self.name)
        origin_dumpxml = minidom.parseString(self.origin.settings)
        _dumpxml = self.create_dumpxml(origin_dumpxml)
        clone_dumpxml_file = utils.write_clone_dumpxml(self.name, _dumpxml)

        return clone_dumpxml_file

    def create_dumpxml(self, clone_xml):
        dumpxml.set_name(clone_xml, self.name)
        dumpxml.set_uuid(clone_xml, uuid4())
        self.mac = self.network.get_free_mac()
        dumpxml.set_mac(clone_xml, self.mac)
        dumpxml.set_disk_file(clone_xml, self.drive_path)
        dumpxml.set_interface_source(clone_xml, self.network.bridge_name)
        return clone_xml

    def define_clone(self, clone_dumpxml_file):
        log_pool.info("Defining from {}".format(clone_dumpxml_file))
        file_handler = open(clone_dumpxml_file, "r")
        self.conn.defineXML(file_handler.read())

    def start_virtual_machine(self, machine):
        log_pool.info("Starting {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.create()

    def shutdown_virtual_machine(self, machine):
        log_pool.info("Shutting down {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.shutdown()

    def destroy_clone(self, machine):
        log_pool.info("Destroying {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.destroy()

    def undefine_clone(self, machine):
        log_pool.info("Undefining {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.undefine()

    def delete_clone_machine(self, machine):
        self.undefine_clone(machine)
        utils.delete_clone_drive(machine)

    def get_virtual_machine_dumpxml(self, machine):
        domain = self.conn.lookupByName(machine)
        raw_xml_string = domain.XMLDesc(0)
        xml = minidom.parseString(raw_xml_string)
        return xml

    def get_origin_dumpxml(self, origin_name):
        return self.get_virtual_machine_dumpxml(origin_name)

    @property
    def vnc_port(self):
        xml = self.get_virtual_machine_dumpxml(self.name)
        graphics = xml.getElementsByTagName('graphics')[0]
        return graphics.getAttribute('port')


class OpenstackClone(Clone):
    def __init__(self, origin, prefix, pool):
        super(OpenstackClone, self).__init__(origin, prefix, pool)
        self.platform = origin.short_name

        from core.utils import openstack_utils
        self.nova_client = openstack_utils.nova_client()
        self.network_client = openstack_utils.neutron_client()

        self.network_id = self.get_network_id()
        self.network_name = self.get_network_name(self.network_id)

    def create(self):
        log_pool.info(
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

                    log_pool.info(
                        "Created openstack {clone} with ip {ip}"
                        " and mac {mac}".format(
                            clone=self.name, ip=self.ip, mac=self.mac)
                    )
            except Exception as e:
                log_pool.info("Vm %s does not have address block. Error: %s" %
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
                log_pool.info(
                    "Can't find vm %s in openstack. Error: %s" %
                    (self.name, e.message)
                )
                server = None

            if server is not None and server.status.lower() in \
                    ('build', 'rebuild'):
                log_pool.info("Virtual Machine %s is spawning..." % self.name)

                if create_check_retry > config_create_check_retry_count:
                    p = config_create_check_retry_count * \
                        config_create_check_pause
                    log_pool.info("VM %s creates more than %s seconds, "
                                  "check this VM" % (self.name, p))

                create_check_retry += 1
                time.sleep(config_create_check_pause)

            elif self.vm_has_created():
                if method is not None:
                    method()
                if self.ping_vm():
                    self.ready = True
                    break
                if ping_retry > config_ping_retry_count:
                    p = config_ping_retry_count * config_ping_timeout
                    log_pool.info("VM %s pings more than %s seconds, "
                                  "rebuilding VM..." % (self.name, p))
                    self.rebuild()
                    break

                ping_retry += 1
            else:
                log_pool.info("VM %s has not been created." % self.name)
                self.rebuild()
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
                    log_pool.info(
                        "Associate vm with network id %s and subnet id %s"
                        % (str(subnet['network_id']), str(subnet['id'])))

            try:
                net_id = stree[self_ip]
                log_pool.info(
                    "Current network id for creating vm: %s" % net_id)
                return net_id
            except KeyError:
                log_pool.info("Error: Network id not found in your project.")
                return None
        else:
            log_pool.info("Error: Your server does not have ip address.")
            return None
            # fixme
            # create new network

    def vm_has_created(self):
        try:
            server = self.nova_client.servers.find(name=self.name)
        except Exception as e:
            log_pool.info(
                "An error occurred during addition ip for vm %s: %s" %
                (self.name, e.message))
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
        except Exception as e:
            log_pool.info("VM does not exist. Error: %s" % e.message)
            return False

    def delete(self, try_to_rebuild=True):
        if try_to_rebuild and self.is_preloaded():
            self.rebuild()
            return

        self.ready = False
        self.pool.remove_vm(self)
        if self.check_vm_exist(self.name):
            try:
                self.nova_client.servers.find(name=self.name).delete()
            except Exception as e:
                log_pool.info("Delete vm %s was FAILED. %s" %
                              (self.name, e.message))
            log_pool.info("Deleted openstack clone: {clone}".format(
                clone=self.name))
        else:
            log_pool.info("VM {clone} can not be removed because "
                          "it does not exist".format(clone=self.name))
        VirtualMachine.delete(self)

    def rebuild(self):
        log_pool.info("Rebuilding openstack {clone}".format(clone=self.name))

        if self.is_preloaded():
            self.pool.remove_vm(self)
            self.pool.pool.append(self)

        self.ready = False
        try:
            self.nova_client.servers.find(name=self.name).rebuild(self.image)
            self._wait_for_activated_service(lambda: log_pool.info(
                "Rebuilded openstack clone: {clone}".format(clone=self.name)))
        except Exception as e:
            log_pool.info(
                "Rebuild vm %s was FAILED. %s" % (self.name, e.message))
            self.delete(try_to_rebuild=False)

from functools import wraps
from threading import Thread
import time

from functools import partial
from xml.dom import minidom
from uuid import uuid4
from novaclient.exceptions import NotFound
import netifaces
import SubnetTree

from . import VirtualMachine
from .virtual_machines_pool import pool

from ..dumpxml import dumpxml
from ..network.network import Network
from ..connection import Virsh
from ..logger import log
from ..utils import utils
from ..utils import openstack_utils
from ..exceptions import libvirtError, CreationException
from ..config import config

from ...core.utils import network_utils
import sys
from Queue import Queue


class BucketThread(Thread):
    def __init__(self, bucket, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.bucket = bucket

    def run(self):
        try:
            super(BucketThread, self).run()
        except:
            self.bucket.put(sys.exc_info())


def threaded_wait(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        def thread_target():
            return func(self, *args, **kwargs)

        error_bucket = Queue()
        tr = BucketThread(target=thread_target, bucket=error_bucket)
        tr.daemon = True
        tr.start()

        while tr.isAlive():
            tr.join(0.1)

        if not error_bucket.empty():
            error = error_bucket.get()
            raise error[0], error[1], error[2]

    return wrapper


class Clone(VirtualMachine):
    def __init__(self, origin, prefix):
        super(Clone, self).__init__()
        self.prefix = prefix
        self.origin = origin
        self.platform = origin.name
        self.ready = False
        self.checking = False

    def __str__(self):
        return "{name}({ip})".format(name=self.name, ip=self.ip)

    @property
    def name(self):
        return "{}-clone-{}".format(self.origin.name, self.prefix)

    def delete(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def rebuild(self):
        raise NotImplementedError

    def ping_vm(self):
        ports = [config.SELENIUM_PORT, config.VMMASTER_AGENT_PORT]
        timeout = config.PING_TIMEOUT
        start = time.time()
        log.info("Starting ping vm {clone}: {ip}:{port}".format(clone=self.name, ip=self.ip, port=ports))
        _ping = partial(network_utils.ping, self.ip)
        while time.time() - start < timeout:
            result = map(_ping, ports)
            if all(result):
                log.info("Successful ping for {clone} with {ip}:{ports}".format(clone=self.name, ip=self.ip, ports=ports))
                break
            time.sleep(0.1)

        result = map(_ping, ports)
        if not all(result):
            fails = [port for port, res in zip(ports, result) if res is False]
            log.info("Failed ping for {clone} with {ip}:{ports}".format(clone=self.name, ip=self.ip, ports=str(fails)))
            return False

        return True


class KVMClone(Clone):
    dumpxml_file = None
    drive_path = None

    def __init__(self, origin, prefix):
        super(KVMClone, self).__init__(origin, prefix)

        self.conn = Virsh()
        self.network = Network()

    def delete(self):
        log.info("deleting kvm clone: {}".format(self.name))
        utils.delete_file(self.drive_path)
        utils.delete_file(self.dumpxml_file)
        try:
            domain = self.conn.lookupByName(self.name)
            domain.destroy()
            domain.undefine()
        except libvirtError:
            # not running
            pass
        try:
            self.network.append_free_mac(self.mac)
        except ValueError, e:
            log.warning(e)
            pass

        pool.remove_vm(self)
        VirtualMachine.delete(self)

    def create(self):
        log.info("creating kvm clone of {platform}".format(platform=self.platform))
        origin = self.platform
        self.dumpxml_file = self.clone_origin(origin)

        self.define_clone(self.dumpxml_file)
        self.start_virtual_machine(self.name)
        self.ip = self.network.get_ip(self.mac)
        self.ready = True

        log.info("created kvm {clone} on ip: {ip} with mac: {mac}".format(clone=self.name, ip=self.ip, mac=self.mac))
        return self

    def rebuild(self):
        log.info("rebuilding kvm clone of {platform}".format(platform=self.platform))

        pool.remove_vm(self)

        if self.checking:
            self.delete()
            self.create()

        pool.add_vm(self)
        log.info("rebuilded kvm {clone} on ip: {ip} with mac: {mac}".format(clone=self.name, ip=self.ip, mac=self.mac))

    def clone_origin(self, origin_name):
        self.drive_path = utils.clone_qcow2_drive(origin_name, self.name)

        origin_dumpxml = minidom.parseString(self.origin.settings)
        dumpxml = self.create_dumpxml(origin_dumpxml)
        clone_dumpxml_file = utils.write_clone_dumpxml(self.name, dumpxml)

        return clone_dumpxml_file

    def create_dumpxml(self, clone_xml):
        # setting clone name
        dumpxml.set_name(clone_xml, self.name)

        # setting uuid
        dumpxml.set_uuid(clone_xml, uuid4())

        # setting mac
        self.mac = self.network.get_free_mac()
        dumpxml.set_mac(clone_xml, self.mac)

        # setting drive file
        dumpxml.set_disk_file(clone_xml, self.drive_path)

        # setting interface
        dumpxml.set_interface_source(clone_xml, self.network.bridge_name)

        return clone_xml

    def define_clone(self, clone_dumpxml_file):
        log.info("defining from {}".format(clone_dumpxml_file))
        file_handler = open(clone_dumpxml_file, "r")
        self.conn.defineXML(file_handler.read())

    def list_virtual_machines(self):
        pass

    def start_virtual_machine(self, machine):
        log.info("starting {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.create()

    def shutdown_virtual_machine(self, machine):
        log.info("shutting down {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.shutdown()

    def destroy_clone(self, machine):
        log.info("destroying {}".format(machine))
        domain = self.conn.lookupByName(machine)
        domain.destroy()

    def undefine_clone(self, machine):
        log.info("undefining {}".format(machine))
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

    def __init__(self, origin, prefix):
        super(OpenstackClone, self).__init__(origin, prefix)
        self.platform = origin.short_name
        self.nova_client = openstack_utils.nova_client()
        self.network_client = openstack_utils.neutron_client()
        self.network_id = self.get_network_id()
        self.network_name = self.get_network_name(self.network_id)

    def create(self):
        log.info("Creating openstack clone of {} with image={}, flavor={}".format(self.name,
                                                                                  self.image,
                                                                                  self.flavor))

        kwargs = {
            'name': self.name,
            'image': self.image,
            'flavor': self.flavor,
            'nics': [{'net-id': self.network_id}]
        }

        if bool(config.OPENSTACK_ZONE_FOR_VM_CREATE):
            kwargs.update({'availability_zone': config.OPENSTACK_ZONE_FOR_VM_CREATE})

        self.nova_client.servers.create(**kwargs)
        self._wait_for_activated_service(self.get_ip)

    def get_ip(self):
        if self.ip is None:
            try:
                addresses = self.nova_client.servers.find(name=self.name).addresses.get(self.network_name, None)
                if addresses is not None:
                    ip = addresses[0].get('addr', None)
                    self.mac = addresses[0].get('OS-EXT-IPS-MAC:mac_addr', None)

                    if ip is not None:
                        self.ip = ip
                    log.info("Created openstack {clone} with ip {ip} and mac {mac}".format(clone=self.name, ip=self.ip, mac=self.mac))
            except Exception as e:
                log.info("Vm %s does not have address block. Error: %s" % (self.name, e.message))

    @threaded_wait
    def _wait_for_activated_service(self, method=None):
        from time import sleep
        config_wait_tries, config_wait_timeout = config.VM_CREATE_CHECK_ATTEMPTS, config.VM_CREATE_CHECK_TIMEOUT
        config_ping_tries, config_ping_timeout = config.PING_ATTEMPTS, config.PING_TIMEOUT

        wait_tries = 1
        ping_tries = 1
        while True:
            try:
                server = self.nova_client.servers.find(name=self.name)
            except Exception as e:
                log.info("Can't find vm %s in openstack. Error: %s" % (self.name, e.message))
                server = None

            if server is not None and server.status.lower() in ('build', 'rebuild'):
                log.info("Virtual Machine %s is spawning..." % self.name)
                if wait_tries > config_wait_tries:
                    log.info("VM %s creates more than %s seconds, check this VM" % (self.name, config_wait_tries*config_wait_timeout))

                wait_tries += 1
                sleep(config_wait_timeout)

            elif self.vm_has_created():
                if method is not None:
                    method()
                if self.ping_vm():
                    self.ready = True
                    break
                if ping_tries > config_ping_tries:
                    log.info("VM %s pings more than %s seconds, deleting VM" % (self.name, config_ping_tries*config_ping_timeout))
                    self.rebuild()
                    break

                ping_tries += 1
                sleep(config_ping_timeout)

            else:
                log.info("VM %s has not been created." % self.name)
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
            raise CreationException('Can\'t return network name because network_id was %s' % str(network_id))

    def get_network_id(self):
        try:
            self_ip = netifaces.ifaddresses('eth0').get(netifaces.AF_INET, [{'addr': None}])[0]['addr']
        except ValueError:
            self_ip = None

        if self_ip:
            stree = SubnetTree.SubnetTree()
            for subnet in self.network_client.list_subnets().get('subnets', []):
                if subnet['tenant_id'] == config.OPENSTACK_TENANT_ID:
                    stree[str(subnet['cidr'])] = str(subnet['network_id'])
                    log.info("Associate vm with network id %s and subnet id %s" % (str(subnet['network_id']),
                                                                                   str(subnet['id'])))

            try:
                net_id = stree[self_ip]
                log.info("Current network id for creating vm: %s" % net_id)
                return net_id
            except KeyError:
                log.info("Error: Network id not found in your project.")
                return None
        else:
            log.info("Error: Your server does not have ip address.")
            return None
            # fixme
            # create new network

    def vm_has_created(self):
        try:
            server = self.nova_client.servers.find(name=self.name)
        except Exception as e:
            log.info("An error occurred during addition ip for vm %s: %s" % (self.name, e.message))
            server = None

        return True if server is not None and str(server.status).lower() == 'active' \
                       and getattr(server, 'addresses', None) is not None else False

    def check_vm_exist(self, server_name):
        try:
            server = self.nova_client.servers.find(name=server_name)
            return True if server.name == server_name else False
        except Exception as e:
            log.info("VM does not exist. Error: %s" % e.message)
            return False

    def delete(self):
        pool.remove_vm(self)
        if self.check_vm_exist(self.name):
            try:
                self.nova_client.servers.find(name=self.name).delete()
            except Exception as e:
                log.info("Delete vm %s was FAILED. %s" % (self.name, e.message))

            log.info("Deleted openstack clone: {clone}".format(clone=self.name))
        else:
            log.info("VM {clone} can not be removed because it does not exist".format(clone=self.name))

    def rebuild(self):
        log.info("Rebuilding openstack {clone}".format(clone=self.name))

        if 'preloaded' in self.name:
            pool.remove_vm(self)
            pool.pool.append(self)

        self.ready = False
        try:
            self.nova_client.servers.find(name=self.name).rebuild(self.image)
            self._wait_for_activated_service(lambda: log.info("Rebuilded openstack {clone}".format(clone=self.name)))
        except Exception as e:
            log.info("Rebuild vm %s was FAILED. %s" % (self.name, e.message))
            self.delete()
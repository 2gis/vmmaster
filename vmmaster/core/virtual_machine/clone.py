from functools import wraps
from threading import Thread
import time

from xml.dom import minidom
from uuid import uuid4
from novaclient.exceptions import NotFound
from netifaces import ifaddresses, AF_INET
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
        return "{}-clone-{}".format(self.platform, self.prefix)

    def delete(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def rebuild(self):
        raise NotImplementedError

    def vm_is_ready(self):
        port = config.SELENIUM_PORT
        timeout = config.PING_TIMEOUT
        start = time.time()
        log.info("Starting ping: {ip}:{port}".format(ip=self.ip, port=port))
        while time.time() - start < timeout:
            if network_utils.ping(self.ip, port):
                log.info("Check is successful for {clone} with {ip}:{port}".format(clone=self.name, ip=self.ip, port=port))
                break

            time.sleep(0.1)

        if not network_utils.ping(self.ip, port):
            log.info("Check is failed for {clone} with {ip}:{port}".format(clone=self.name, ip=self.ip, port=port))
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

    def vm_is_ready(self):
        return super(KVMClone, self).vm_is_ready()

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
        self.nova_client = openstack_utils.nova_client()
        self.network_client = openstack_utils.neutron_client()
        self.network_id = self.get_network_id()
        self.network_name = self.get_network_name(self.network_id)

    def create(self):
        log.info("creating openstack clone of {} with image={}, flavor={}".format(self.platform,
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

        try:
            self.nova_client.servers.create(**kwargs)
        except Exception as e:
            log.info("Creating error: %s" % e)

        def get_ip():
            if self.check_vm_exist(self.name):
                server = self.nova_client.servers.find(name=self.name)
                addresses = server.addresses.get(self.network_name, None)

                if addresses is not None:
                    ip = addresses[0].get('addr', None)
                    self.mac = addresses[0].get('OS-EXT-IPS-MAC:mac_addr', None)

                    if ip is not None:
                        self.ip = ip

                log.info("created openstack {clone} on ip: {ip} with mac: {mac}".format(clone=self.name, ip=self.ip, mac=self.mac))
        self._wait_for_activated_service(get_ip)

    @threaded_wait
    def _wait_for_activated_service(self, method=None, tries=10, timeout=5):
        from time import sleep
        i = 0
        while True:
            if self.vm_is_ready():
                if method is not None:
                    method()
                self.ready = True
                break
            else:
                if i > tries:
                    log.info("VM %s has not been created." % self.name)
                    self.delete()
                    pool.remove_vm(self)

                i += 1
                log.info('Status for %s is not active, wait for %ss. before next try...' % (self.name, timeout))
                sleep(timeout)

    @property
    def image(self):
        return self.nova_client.images.find(name=self.platform)

    @property
    def flavor(self):
        return self.nova_client.flavors.find(name=self.origin.flavor_name)

    def get_network_name(self, network_id):
        for net in self.network_client.list_networks().get('networks', []):
            if net['id'] == network_id:
                return net['name']

    def get_network_id(self):
        try:
            self_ip = ifaddresses('eth0').get(AF_INET, [{'addr': None}])[0]['addr']
        except ValueError:
            self_ip = None

        if self_ip:
            stree = SubnetTree.SubnetTree()
            for subnet in self.network_client.list_subnets()['subnets']:
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
            log.info("Error: Your server have not ip address.")
            pass
            # fixme
            # create new network

    def vm_is_ready(self):
        try:
            server = self.nova_client.servers.find(name=self.name)
        except Exception as e:
            log.info("VM %s not found in openstack. Error message: %s" % (self.name, e.message))
            server = None
        return True if server is not None and str(server.status).lower() == 'active' \
                       and getattr(server, 'addresses', None) is not None else False

    def check_vm_exist(self, server_name):
        try:
            return bool(self.nova_client.servers.find(name=server_name))
        except NotFound:
            return False

    def delete(self):
        if self.check_vm_exist(self.name):
            log.info("deleting openstack clone: {clone}".format(clone=self.name))
            pool.remove_vm(self)

            try:
                self.nova_client.servers.find(name=self.name).delete()
            except Exception as e:
                log.info("Delete vm %s was FAILED. %s" % (self.name, e.message))

            log.info("deleted openstack clone: {clone}".format(clone=self.name))
        else:
            log.info("{clone} can not be removed because it does not exist".format(clone=self.name))

    def rebuild(self):
        log.info("rebuilding openstack {clone}".format(clone=self.name))

        pool.remove_vm(self)
        pool.pool.append(self)

        self.ready = False
        try:
            self.nova_client.servers.find(name=self.name).rebuild(self.image)
        except Exception as e:
            log.info("Rebuild vm %s was FAILED. %s" % (self.name, e.message))
            self.delete()

        def is_succesful():
            log.info("rebuilded openstack {clone}".format(clone=self.name))

        self._wait_for_activated_service(is_succesful)
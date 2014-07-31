from xml.dom import minidom
from uuid import uuid4

from ..dumpxml import dumpxml
from ..network.network import Network
from ..connection import Virsh
from ..logger import log
from ..utils import utils
from ..exceptions import libvirtError
from .virtual_machine import VirtualMachine


class Clone(VirtualMachine):
    name = None
    mac = None
    ip = None

    dumpxml_file = None
    drive_path = None

    def __init__(self, number, origin):
        self.number = number
        self.origin = origin
        self.platform = origin.name
        self.name = self.platform + "-clone" + str(self.number)
        self.conn = Virsh()
        self.network = Network()

    def delete(self):
        log.info("deleting clone: {}".format(self.name))
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
        super(Clone, self).delete()

    def create(self):
        log.info("creating clone of {platform}".format(platform=self.platform))
        origin = self.platform
        self.dumpxml_file = self.clone_origin(origin)

        self.define_clone(self.dumpxml_file)
        self.start_virtual_machine(self.name)
        self.ip = self.network.get_ip(self.mac)
        log.info("created {clone} on ip: {ip}".format(clone=self.name, ip=self.ip))
        return self

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
from xml.dom import minidom

import libvirt
import virtinst.util

from vmmaster.core.dumpxml import dumpxml
from vmmaster.core.network.network import Network
from vmmaster.utils import utils
from config import Config


class Clone(object):
    def __init__(self, number, platform):
        self.hypervisor = 'qemu:///system'
        self.conn = libvirt.open(self.hypervisor)
        self.number = number
        self.platfrom = platform
        self.network = Network(self.conn)

    def create(self):
        origin = self.platfrom
        clone_name, clone_dumpxml = self.clone_origin(origin)
        self.define_clone(clone_dumpxml)
        self.start_virtual_machine(clone_name)
        return self.get_clone_ip(clone_name)

    def clone_origin(self, origin_name):
        clone_name = origin_name + "-clone" + str(self.number)
        clone_drive_path = utils.create_qcow2_clone(origin_name, clone_name)

        origin_dumpxml = self.get_origin_dumpxml(origin_name)
        clone_dumpxml = self.create_dumpxml(origin_dumpxml, clone_name, clone_drive_path)
        clone_dumpxml_file = utils.write_clone_dumpxml(clone_name, clone_dumpxml)

        return clone_name, clone_dumpxml_file

    def create_dumpxml(self, clone_xml, clone_name, clone_drive_path):
        # setting clone name
        dumpxml.set_name(clone_xml, clone_name)

        # setting uuid
        u = virtinst.util.randomUUID()
        uuid = virtinst.util.uuidToString(u)
        dumpxml.set_uuid(clone_xml, uuid)

        # setting mac
        clone_mac = self.network.get_free_mac()
        dumpxml.set_mac(clone_xml, clone_mac)

        clone_path_temp = clone_drive_path

        # setting drive file
        dumpxml.set_disk_file(clone_xml, clone_drive_path)

        clone_path = clone_path_temp

        # setting interface
        dumpxml.set_interface_source(clone_xml, self.network.bridge_name)

        return clone_xml

    def define_clone(self, clone_dumpxml_file):
        print "defining from {}".format(clone_dumpxml_file)
        file_handler = open(clone_dumpxml_file, "r")
        self.conn.defineXML(file_handler.read())

    def list_virtual_machines(self):
        pass

    def start_virtual_machine(self, machine):
        print "starting {}".format(machine)
        domain = self.conn.lookupByName(machine)
        domain.create()

    def shutdown_virtual_machine(self, machine):
        print "shutting down {}".format(machine)
        domain = self.conn.lookupByName(machine)
        domain.shutdown()

    def destroy_clone(self, machine):
        print "destroying {}".format(machine)
        domain = self.conn.lookupByName(machine)
        domain.destroy()

    def undefine_clone(self, machine):
        print "undefining {}".format(machine)
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
        origin_vm_name = "{origin_name}-{postfix}".format(
            origin_name=origin_name,
            postfix=Config.ORIGIN_POSTFIX)
        return self.get_virtual_machine_dumpxml(origin_vm_name)

    def get_clone_ip(self, clone_name):
        xml = self.get_virtual_machine_dumpxml(clone_name)
        mac = dumpxml.get_mac(xml)
        return self.network.get_ip(mac)
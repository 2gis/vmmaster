# depends on packages: kvm
import os

import libvirt
from xml.dom import minidom

# paths
from vmmaster.core import dumpxml
from vmmaster.core.network.network import Network

from config import Config
from vmmaster.utils import utils


class CloneManager(object):
    clone_list = []

    def __init__(self):
        # virtualization
        self.hypervisor = 'qemu:///system'
        self.conn = libvirt.open(self.hypervisor)
        # network
        self.network = Network(self.conn)

    def __del__(self):
        self.network.__del__()
        for clone_name, clone_files in self.clone_list:
            domain = self.conn.lookupByName(clone_name)
            domain.destroy()
            domain.undefine()
            for file in clone_files:
                try:
                    os.remove(file)
                except (OSError, AttributeError):
                    pass

    def create_clone_dumpxml(self, clone_xml, clone_name, clone_path):
        # setting clone name
        dumpxml.set_name(clone_xml, clone_name)

        # setting uuid
        import virtinst.util

        u = virtinst.util.randomUUID()
        uuid = virtinst.util.uuidToString(u)
        dumpxml.set_uuid(clone_xml, uuid)

        # setting mac
        clone_mac = self.network.get_free_mac()
        dumpxml.set_mac(clone_xml, clone_mac)

        clone_path_temp = clone_path

        # setting drive file
        #clone_path = "/home/vmmaster/vmmaster/origins/ubuntu-13.04-x64-origin.qcow2"
        dumpxml.set_disk_file(clone_xml, clone_path)

        clone_path = clone_path_temp

        # setting interface
        dumpxml.set_interface_source(clone_xml, self.network.bridge_name)

        # saving to dir
        clone_dumpxml_file = "{dir_path}/{clone_name}.xml".format(
            dir_path=os.path.dirname(clone_path),
            clone_name=clone_name
        )
        file_handler = open(clone_dumpxml_file, "w")
        clone_xml.writexml(file_handler)
        return clone_dumpxml_file

    def clone_virtual_machine(self, origin_name):
        clone_name = origin_name + "-clone" + str(len(self.clone_list))

        clone_path = utils.create_qcow2_clone(origin_name, clone_name)
        # os.chmod(clone_path, 0777)

        origin_xml = self.get_origin_dumpxml(origin_name)
        clone_dumpxml_file = self.create_clone_dumpxml(origin_xml, clone_name, clone_path)

        self.clone_list.append((clone_name, [clone_path, clone_dumpxml_file]))
        return clone_name, clone_dumpxml_file

    def define_clone(self, clone_dumpxml_file):
        print "defining from {}".format(clone_dumpxml_file)
        file_handler = open(clone_dumpxml_file, "r")
        self.conn.defineXML(file_handler.read())

    def list_virtual_machines(self):
        pass

    def start_virtual_machine(self, machine):
        print "starting {}".format(machine)
        domain = self.conn.lookupByName(machine)
        # try:
        domain.create()
        # except libvirt.libvirtError:
        #     pass

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
__author__ = 'i.pavlov'
# depends on packages: kvm


import os

import libvirt
from xml.dom import minidom

import NetworkUtils
import SystemUtils

import time

# paths
project_root = os.path.dirname(os.path.abspath(__file__)) + "/"

# virtualization
hypervisor = 'qemu:///system'
conn = libvirt.open(hypervisor)

# vm grid
VIRTUAL_MACHINE_MAX = 10
grid = []


def manage_clone_machines_grid(standard_machine):
    if grid[standard_machine]:
        # find which number from 0 to n is free
        pass
    else:
        # create new part of grid
        pass


def clone_virtual_machine(standard_machine):
    clone_name = "temp_ubuntu"
    clone_drive_name = clone_name + ".img"

    print "cloning {} into {}".format(standard_machine, clone_name)
    #phrase = "hello {}!".format(machine)
    SystemUtils.run_command(
        ["sudo", "virt-clone", "-o", standard_machine, "-n", clone_name, "-f", clone_drive_name,
         "--connect={}".format(hypervisor)])
    return clone_name


def list_virtual_machines():
    pass


def start_virtual_machine(machine):
    print "starting {}".format(machine)
    domain = conn.lookupByName(machine)
    try:
        domain.create()
    except libvirt.libvirtError:
        pass

    print "start sleep"
    #time.sleep(30)
    print "stop sleep"
    #SystemUtils.run_command(["virsh", "-c", "qemu:///system", "start", machine])


def shutdown_virtual_machine(machine):
    print "shutting down {}".format(machine)
    domain = conn.lookupByName(machine)
    domain.shutdown()


def destroy_virtual_machine(machine):
    print "destroying {}".format(machine)
    domain = conn.lookupByName(machine)
    domain.destroy()
    #SystemUtils.run_command(["virsh", "-c", "qemu:///system", "destroy", machine])


def undefine_virtual_machine(machine):
    print "undefining {}".format(machine)
    domain = conn.lookupByName(machine)
    domain.undefine()
    #SystemUtils.run_command(["virsh", "-c", "qemu:///system", "undefine", machine])


def delete_temp_virtual_drive(machine):
    drive_name = machine + ".img"
    SystemUtils.run_command(["rm", "-f", drive_name])


def delete_virtual_machine(machine):
    undefine_virtual_machine(machine)
    delete_temp_virtual_drive(machine)


def get_virtual_machine_dumpxml(machine):
    domain = conn.lookupByName(machine)
    raw_xml = domain.XMLDesc(0)
    xml = minidom.parseString(raw_xml)
    return xml


def get_virtual_machine_mac(machine):
    xml = get_virtual_machine_dumpxml(machine)
    mac = xml.getElementsByTagName('mac')
    return mac[0].getAttribute('address')


def get_virtual_machine_ip(machine):
    mac = get_virtual_machine_mac(machine)
    return NetworkUtils.get_ip_by_mac(mac)


#temp_virtual = clone_virtual_machine("ubuntu-13.04-x64")
temp_virtual = "temp_ubuntu"
start_virtual_machine(temp_virtual)
print "ip address for {} is {}".format(temp_virtual, get_virtual_machine_ip(temp_virtual))
#destroy_virtual_machine(temp_virtual)
# delete_virtual_machine(temp_virtual)

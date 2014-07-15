# vmmaster
[![Build Status](https://travis-ci.org/nwlunatic/vmmaster.svg)](https://travis-ci.org/nwlunatic/vmmaster)

## dependenies:
+ nmap
+ libvirt
+ netifaces

## install
```bash
sudo -E pip install -U git+https://github.com/nwlunatic/vmmaster.git#egg=vmmaster
```

## commands to create qcow2 VM's origins
### create qcow2 drive
```bash
qemu-img create -f qcow2 -o preallocation=metadata ubuntu-13.04-x64-origin.qcow2 8G
```
### install ubuntu from iso
```bash
sudo virt-install --connect=qemu:///system --name ubuntu-13.04-x64-origin --network=bridge:virbr0 --ram 2048 --vcpus 2 --disk path=/home/vmmaster/vmmaster/origins/ubuntu-13.04-x64-origin.qcow2,format=qcow2,bus=virtio,cache=none --cdrom /home/vmmaster/ubuntu-13.04-desktop-amd64.iso --vnc --accelerate --os-type=linux --os-variant=generic26 --hvm
```
### install windows from iso
```bash
sudo virt-install --connect=qemu:///system --name windows-7-x64-origin --network=bridge:virbr0 --ram 2048 --vcpus 2 --disk path=/home/vmmaster/vmmaster/origins/windows-7-x64-origin.qcow2,format=qcow2,bus=virtio,cache=none --cdrom /home/vmmaster/Win7x64sp1oem.iso --disk path=/home/vmmaster/virtio-win-0.1-65.iso,device=cdrom,perms=ro --vnc --accelerate --os-type=windows --os-variant=win7 --hvm
```

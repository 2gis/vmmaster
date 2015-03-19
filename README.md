# vmmaster
[![Build Status](https://travis-ci.org/2gis/vmmaster.svg)](https://travis-ci.org/2gis/vmmaster)

## dependencies:
+ libvirt
+ kvm
+ postgresql
+ libpq-dev
+ python-psycopg2

## install
### manual

```bash
pip install -U git+https://github.com/2gis/vmmaster.git#egg=vmmaster
vmmaster init
```

### ansible

[how to install vmmaster using Ansible?](deploy/README.md)

## commands to create qcow2 VM's origins
### create qcow2 drive

```bash
qemu-img create -f qcow2 -o preallocation=metadata ubuntu-13.04-x64-origin.qcow2 8G
```
### install ubuntu from iso

```bash
sudo virt-install --connect=qemu:///system --name ubuntu-13.04-x64-origin --network=bridge:virbr0 --ram 2048 --vcpus 2 --disk path=$VMMASTER_HOME/origins/ubuntu-13.04-x64/drive.qcow2,format=qcow2,bus=virtio,cache=none --cdrom $ISO_PLACE/ubuntu-13.04-desktop-amd64.iso --vnc --accelerate --os-type=linux --os-variant=generic26 --hvm
```

### generate settings.xml
TODO


Welcome to vmmaster's documentation!
====================================

Dependencies
============
* tox
* postgresql

Installation
============

::

    user@machine: git clone https://github.com/2gis/vmmaster.git
    user@machine: cd vmmaster
    user@machine: chmod +x install_dependencies.sh
    user@machine: ./install_dependencies.sh
    user@machine: sudo pip install tox
    user@machine: tox
    user@machine: mv ./config_template.py config.py
    user@machine: sudo .tox/bin/python manage.py init
    user@machine: .tox/bin/python manage.py migrations
    user@machine: .tox/bin/python manage.py runserver


Extensions
==========
* `Client for vmmaster's virtual machine <https://github.com/2gis/vmmaster-client>`_
* `Django-application for vmmaster <https://github.com/2gis/vmmaster-frontend>`_


Commands to create qcow2 VM's origins
=====================================

1. create qcow2 drive::

    qemu-img create -f qcow2 -o preallocation=metadata ubuntu-13.04-x64-origin.qcow2 8G
2. install ubuntu from iso::

    sudo virt-install --connect=qemu:///system --name ubuntu-13.04-x64-origin --network=bridge:virbr0 --ram 2048 --vcpus 2 --disk path=$VMMASTER_HOME/origins/ubuntu-13.04-x64/drive.qcow2,format=qcow2,bus=virtio,cache=none --cdrom $ISO_PLACE/ubuntu-13.04-desktop-amd64.iso --vnc --accelerate --os-type=linux --os-variant=generic26 --hvm
3. generate settings.xml::

    todo

Contents:
=========

.. toctree::
   :maxdepth: 2

   development
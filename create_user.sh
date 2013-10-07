#!/bin/bash

# useradd vmmaster
pass=$(perl -e 'print crypt("vmmaster", "password")')
sudo useradd --create-home --home-dir=/var/lib/vmmaster -p $pass --groups=libvirtd --shell=/bin/bash vmmaster

# install dependencies
sudo apt-get install daemon python-pip python-dev virtinst virt-viewer


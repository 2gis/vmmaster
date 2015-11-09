#!/bin/bash

# enable cloud-archive to get the latest libvirt
sudo apt-get -y install python-software-properties
sudo add-apt-repository -y cloud-archive:icehouse

sudo apt-get update

# install kvm with libvirt
sudo apt-get -y install qemu-kvm libvirt-bin

# install libvirt dependencies
sudo apt-get -y install libvirt-dev

# install openstack dependencies
sudo apt-get -y install libssl-dev libffi-dev

# install postgres dependencies
sudo apt-get install -y libpq-dev

# install vnc_recorder deps
sudo apt-get install -y libav-tools
sudo apt-get install -y cpulimit
#!/bin/bash

# enable cloud-archive to get the latest libvirt
sudo apt-get -y install python-software-properties
sudo add-apt-repository -y cloud-archive:icehouse

sudo apt-get update

# install kvm with libvirt
sudo apt-get -y install qemu-kvm

# install libvirt dependencies
sudo apt-get -y --force-yes install libvirt-dev libvirt-bin

# install openstack dependencies
sudo apt-get -y install libssl-dev libffi-dev

# install postgres dependencies
sudo apt-get install -y libpq-dev

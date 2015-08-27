#!/bin/bash

# install dependencies
sudo apt-get update

# enable cloud-archive to get the latest libvirt
sudo apt-get -y install python-software-properties
sudo add-apt-repository -y cloud-archive:icehouse

# install kvm with libvirt
sudo apt-get -y install qemu-kvm libvirt-bin

# install libvirt-dev for python bindings
sudo apt-get install libvirt-dev
sudo apt-get -y install libvirt-dev

# install openstack dependencies
sudo apt-get -y install libssl-dev libffi-dev
#sudo apt-get install build-essential  virtinst libvirt-bin libvirt-dev kvm

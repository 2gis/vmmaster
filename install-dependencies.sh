#!/bin/bash

# install dependencies
sudo apt-get update

# install kvm with libvirt
sudo apt-get -y install qemu-kvm libvirt-bin 
# install libvirt-dev for python bindings
sudo apt-get -y install libvirt-dev

# install openstack dependencies
sudo apt-get -y install libssl-dev libffi-dev
#sudo apt-get install build-essential  virtinst libvirt-bin libvirt-dev kvm

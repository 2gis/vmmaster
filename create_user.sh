#!/bin/bash

# useradd vmmaster
sudo adduser vmmaster libvirtd

# install dependencies
sudo apt-get install daemon virtinst virt-viewer


#!/bin/bash

sudo apt-get -y install python-software-properties
sudo apt-get update

# install openstack dependencies
sudo apt-get -y install libssl-dev libffi-dev

# install postgres dependencies
sudo apt-get install -y libpq-dev

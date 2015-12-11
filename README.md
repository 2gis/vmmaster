# vmmaster
[![Build Status](https://travis-ci.org/2gis/vmmaster.svg?branch=master)](https://travis-ci.org/2gis/vmmaster)
[![Coverage](https://codecov.io/github/2gis/vmmaster/coverage.svg?branch=master)](https://codecov.io/github/2gis/vmmaster?branch=master)

## dependencies:
+ tox
+ postgresql

## install
### manual

#### run vmmaster
```bash
user@machine: chmod +x install_dependencies.sh
user@machine: ./install_dependencies.sh
user@machine: sudo pip install tox
user@machine: tox
user@machine: mv ./config_template.py config.py
user@machine: sudo .tox/bin/python manage.py init
user@machine: .tox/bin/python manage.py migrations
user@machine: .tox/bin/python manage.py runserver
```

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

## development

### environment
pip install -r requirements-dev.txt
./install-hooks.sh

### linting
+ .tox/bin/flake8 vmmaster/ tests/

### unittests with coverage
+ .tox/bin/coverage run --source=vmmaster,vmpool,core run_unittests.py
+ .tox/bin/coverage html
+ look for coverage/index.html

## Documentation
More [information](http://vmmaster.readthedocs.org)

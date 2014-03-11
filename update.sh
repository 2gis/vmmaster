#!/usr/bin/env bash

# check virtualenv is installed
hash virtualenv 2>/dev/null || { echo >&2 "virtualenv is not installed.  Aborting."; exit 1; }


# clear the environment
rm -rf .env

# making all in .env
virtualenv .env
source .env/bin/activate

mkdir .env/etc/
mkdir .env/etc/init
#rm -rf .env/lib/python2.7/site-packages/urlgrabber
#rm -f .env/lib/python2.7/site-packages/libvirt*

pip install -U ../vmmaster
pip install -U git+https://github.com/nwlunatic/lode_runner

# install hard to include for now in setup.py dependecies
cp /usr/lib/python2.7/dist-packages/libvirt* .env/lib/python2.7/site-packages/
cp /usr/lib/python2.7/dist-packages/libxml2* .env/lib/python2.7/site-packages/
cp -r /usr/lib/python2.7/dist-packages/urlgrabber .env/lib/python2.7/site-packages/
cp -r /usr/lib/python2.7/dist-packages/virtinst .env/lib/python2.7/site-packages/

export PYCURL_SSL_LIBRARY=gnutls
pip install -U pycurl

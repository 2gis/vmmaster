# -*- coding: utf-8 -*-


import logging
from keystoneauth1 import session
from keystoneauth1.identity import v3
from keystoneclient.v3 import client as ksclient
from novaclient import client as novaclient

from core.config import config


OPENSTACK_UTILS_LOG_LEVEL = logging.WARNING

OPENSTACK_AUTH_URL = '{}:{}/{}'.format(
    config.OPENSTACK_AUTH_URL,
    config.OPENSTACK_PORT,
    config.OPENSTACK_CLIENT_VERSION
)

logging.getLogger("requests").setLevel(OPENSTACK_UTILS_LOG_LEVEL)
logging.getLogger("keystoneauth").setLevel(OPENSTACK_UTILS_LOG_LEVEL)
logging.getLogger("novaclient").setLevel(OPENSTACK_UTILS_LOG_LEVEL)


def get_session():
    auth = v3.Password(
        auth_url=OPENSTACK_AUTH_URL,
        username=config.OPENSTACK_USERNAME,
        password=config.OPENSTACK_PASSWORD,
        project_name=config.OPENSTACK_TENANT_NAME,
        user_domain_name=config.OPENSTACK_DOMAIN_NAME,
        project_domain_name=config.OPENSTACK_DOMAIN_NAME,
    )
    return session.Session(auth=auth)


def keystone_client():
    return ksclient.Client(session=get_session())


def nova_client():
    return novaclient.Client(
        version="2",
        session=get_session()
    )

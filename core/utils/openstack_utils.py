import keystoneclient.v2_0.client as ksclient
from novaclient.v2.client import client as novaclient
from neutronclient.v2_0 import client as networkclient
import glanceclient.v2.client as glclient
from core.config import config
import logging


def keystone_client():
    keystone_log = logging.getLogger("keystoneclient.auth.identity.v2")
    keystone_log.setLevel(logging.WARNING)
    auth_url = '%s:%s/%s' % (
        config.OPENSTACK_AUTH_URL,
        config.OPENSTACK_PORT,
        config.OPENSTACK_CLIENT_VERSION
    )
    return ksclient.Client(
        auth_url=auth_url,
        username=config.OPENSTACK_USERNAME,
        password=config.OPENSTACK_PASSWORD,
        tenant_name=config.OPENSTACK_TENANT_NAME
    )


def nova_client():
    keystone_log = logging.getLogger("novaclient")
    keystone_log.setLevel(logging.WARNING)
    auth_url = '%s:%s/%s' % (
        config.OPENSTACK_AUTH_URL,
        config.OPENSTACK_PORT,
        config.OPENSTACK_CLIENT_VERSION
    )
    return novaclient.Client(
        version='2',
        username=config.OPENSTACK_USERNAME,
        api_key=config.OPENSTACK_PASSWORD,
        project_id=config.OPENSTACK_TENANT_NAME,
        auth_url=auth_url
    )


def glance_client():
    glance_log = logging.getLogger("glanceclient.common.http")
    glance_log.setLevel(logging.WARNING)
    keystone = keystone_client()
    glance_endpoint = keystone.service_catalog.url_for(service_type='image')
    return glclient.Client(
        glance_endpoint,
        token=keystone.auth_token
    )


def neutron_client():
    neutron_log = logging.getLogger("neutronclient.client")
    neutron_log.setLevel(logging.WARNING)
    keystone = keystone_client()
    network_endpoint = keystone.service_catalog.url_for(service_type='network')
    return networkclient.Client(
        endpoint_url=network_endpoint,
        token=keystone.auth_token
    )

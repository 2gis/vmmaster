import keystoneclient.v2_0.client as ksclient
from novaclient.v2.client import client as novaclient
import glanceclient.v2.client as glclient
from ..config import config


def keystone_client():
    return ksclient.Client(auth_url='%s:%s/%s' % (config.OPENSTACK_AUTH_URL,
                                                  config.OPENSTACK_PORT,
                                                  config.OPENSTACK_CLIENT_VERSION),
                           username=config.OPENSTACK_USERNAME,
                           password=config.OPENSTACK_PASSWORD,
                           tenant_name=config.OPENSTACK_TENANT_NAME)


def nova_client():
    return novaclient.Client(version='2',
                             username=config.OPENSTACK_USERNAME,
                             api_key=config.OPENSTACK_PASSWORD,
                             project_id=config.OPENSTACK_TENANT_NAME,
                             auth_url='%s:%s/%s' % (config.OPENSTACK_AUTH_URL,
                                                    config.OPENSTACK_PORT,
                                                    config.OPENSTACK_CLIENT_VERSION))


def glance_client():
    keystone = keystone_client()
    glance_endpoint = keystone.service_catalog.url_for(service_type='image')
    return glclient.Client(glance_endpoint, token=keystone.auth_token)

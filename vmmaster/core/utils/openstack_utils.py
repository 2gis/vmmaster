import keystoneclient.v2_0.client as ksclient
from novaclient import client as novaclient
import glanceclient.v2.client as glclient
from ..config import config


def keystone_client():
    return ksclient.Client(auth_url='%s:5000/v2.0' % config.OPENSTACK_AUTH_URL,
                           username=config.OPENSTACK_USERNAME,
                           password=config.OPENSTACK_PASSWORD,
                           tenant_name=config.OPENSTACK_TENANT_NAME)


def nova_client():
    return novaclient.Client(version='2',
                             username=config.OPENSTACK_USERNAME,
                             api_key=config.OPENSTACK_PASSWORD,
                             project_id=config.OPENSTACK_TENANT_NAME,
                             auth_url='%s:5000/v2.0' % config.OPENSTACK_AUTH_URL)  # fixme hot and port


def glance_client():
    keystone = keystone_client()
    glance_endpoint = keystone.service_catalog.url_for(service_type='image')
    return glclient.Client(glance_endpoint, token=keystone.auth_token)
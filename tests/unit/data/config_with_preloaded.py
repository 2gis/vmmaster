import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9001

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/logs"

    SCREENSHOTS_DIR = BASE_DIR + "/vmmaster/screenshots"

    # clones related stuff
    ORIGIN_POSTFIX = "origin"

    # kvm
    USE_KVM = False
    KVM_MAX_VM_COUNT = 2
    KVM_PRELOADED = {
        # "ubuntu-14.04-x64": 1
    }

    # openstack
    USE_OPENSTACK = True
    OPENSTACK_MAX_VM_COUNT = 1
    OPENSTACK_PRELOADED = {
        'origin_1': 1,
    }

    OPENSTACK_AUTH_URL = "localhost"
    OPENSTACK_PORT = 5000
    OPENSTACK_CLIENT_VERSION = "v2.0"
    OPENSTACK_USERNAME = "user"
    OPENSTACK_PASSWORD = "password"
    OPENSTACK_TENANT_NAME = "test"
    OPENSTACK_TENANT_ID = 1
    OPENSTACK_ZONE_FOR_VM_CREATE = ""
    OPENSTACK_PLATFORM_NAME_PREFIX = "test_"
    OPENSTACK_PING_RETRY_COUNT = 1
    OPENASTACK_VM_META_DATA = {
        'admin_pass': 'testPassw0rd.'
    }

    VM_CHECK = False
    VM_CHECK_FREQUENCY = 1800
    VM_CREATE_CHECK_PAUSE = 5
    VM_CREATE_CHECK_ATTEMPTS = 1000
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    # vm pool
    GET_VM_TIMEOUT = 1
    VM_POOL_PORT = 9999
    VM_POOL_HOST = 'localhost'

    # GRAPHITE = ('graphite', 2003)

    SELENIUM_PORT = 4455
    VMMASTER_AGENT_PORT = 9000

    LOG_LEVEL = "INFO"

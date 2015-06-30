import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9000

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/log"

    SCREENSHOTS_DIR = BASE_DIR + "/screenshots"

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
    OPENSTACK_PRELOADED = {}

    OPENSTACK_AUTH_URL = "localhost"
    OPENSTACK_PORT = 5000
    OPENSTACK_CLIENT_VERSION = "v2.0"
    OPENSTACK_USERNAME = "user"
    OPENSTACK_PASSWORD = "password"
    OPENSTACK_TENANT_NAME = "test"
    OPENSTACK_TENANT_ID = 1
    OPENSTACK_ZONE_FOR_VM_CREATE = "zone"
    OPENSTACK_PLATFORM_NAME_PREFIX = "test_"
    OPENSTACK_PING_RETRY_COUNT = 1
    OPENASTACK_VM_META_DATA = {
        'admin_pass': 'testPassw0rd.'
    }

    VM_CHECK = False
    VM_CHECK_FREQUENCY = 1800
    VM_CREATE_CHECK_PAUSE = 1
    VM_CREATE_CHECK_ATTEMPTS = 1
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 180
    PING_TIMEOUT = 1

    GRAPHITE = ('graphite', 2003)

    SELENIUM_PORT = 4455
    VMMASTER_AGENT_PORT = 9000

    LOG_LEVEL = "INFO"

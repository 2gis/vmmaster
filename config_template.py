import os


class Config(object):
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9001

    # PostgreSQL dbname
    DATABASE = "postgresql+psycopg2://vmmaster:vmmaster@localhost/testdb"

    CLONES_DIR = os.sep.join([BASEDIR, "clones"])
    ORIGINS_DIR = os.sep.join([BASEDIR, "origins"])
    SESSION_DIR = os.sep.join([BASEDIR, "session"])

    # screenshots
    SCREENSHOTS_DIR = os.sep.join([BASEDIR, "screenshots"])
    SCREENSHOTS_DAYS = 7

    # logging
    LOG_TYPE = "logstash"
    LOG_LEVEL = "DEBUG"

    # kvm
    USE_KVM = True
    KVM_MAX_VM_COUNT = 2
    KVM_PRELOADED = {
        # "ubuntu-14.04-x64": 1
    }

    # openstack
    USE_OPENSTACK = False
    OPENSTACK_MAX_VM_COUNT = 2
    OPENSTACK_PRELOADED = {
        # "ubuntu-14.04-x64": 1
    }

    OPENSTACK_AUTH_URL = "localhost"
    OPENSTACK_PORT = 5000
    OPENSTACK_CLIENT_VERSION = "v2.0"
    OPENSTACK_USERNAME = "user"
    OPENSTACK_PASSWORD = "password"
    OPENSTACK_TENANT_NAME = "test"
    OPENSTACK_DOMAIN_NAME = "test_domain"

    OPENSTACK_TENANT_ID = ""
    OPENSTACK_NETWORK_ID = ""
    OPENSTACK_NETWORK_NAME = ""
    OPENSTACK_ZONE_FOR_VM_CREATE = ""
    OPENSTACK_PLATFORM_NAME_PREFIX = "origin-"
    OPENSTACK_PING_RETRY_COUNT = 3
    OPENSTACK_DEFAULT_FLAVOR = ''
    OPENASTACK_VM_META_DATA = {
        'admin_pass': 'testPassw0rd.'
    }
    OPENSTACK_VM_USERDATA_FILE_PATH = "%s/userdata" % os.path.abspath(os.curdir)

    VM_CREATE_CHECK_PAUSE = 5
    VM_CREATE_CHECK_ATTEMPTS = 1000
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    # vm pool
    GET_VM_TIMEOUT = 180

    # selenium
    SELENIUM_PORT = 4455
    VMMASTER_AGENT_PORT = 9000

    THREAD_POOL_MAX = 100

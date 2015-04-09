import os


class Config(object):
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9000

    # PostgreSQL dbname
    DATABASE = "postgresql+psycopg2://vmmaster:vmmaster@localhost/testdb"

    CLONES_DIR = BASEDIR + "/clones"
    ORIGINS_DIR = BASEDIR + "/origins"
    SESSION_DIR = BASEDIR + "/session"

    # screenshots
    SCREENSHOTS_DIR = BASEDIR + "/screenshots"
    SCREENSHOTS_DAYS = 7

    # logging
    LOG_DIR = BASEDIR + "/log"
    LOG_SIZE = 5242880

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
    OPENSTACK_TENANT_ID = ""
    OPENSTACK_ZONE_FOR_VM_CREATE = ""
    OPENSTACK_PLATFORM_NAME_PREFIX = "origin-"

    VM_CHECK = False
    VM_CHECK_FREQUENCY = 1800
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    # additional logging
    # GRAYLOG = ('logserver', 12201)

    # graphite
    # GRAPHITE = ('graphite', 2003)

    # selenium
    SELENIUM_PORT = "4455"
    VMMASTER_AGENT_PORT = "9000"

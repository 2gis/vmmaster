import os
from tests.helpers import get_free_port


class Config(object):
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
    PORT = get_free_port()

    # PostgreSQL dbname
    DATABASE = "postgresql://vmmaster:vmmaster@localhost/vmmaster_db"
    ENDPOINT_THREADPOOL_PROCESSES = 1

    # screenshots
    SCREENSHOTS_DIR = os.sep.join([BASEDIR, "screenshots"])
    SCREENSHOTS_DAYS = 7

    # logging
    LOG_TYPE = "plain"
    LOG_LEVEL = "DEBUG"

    PLATFORMS = {}

    # openstack
    USE_OPENSTACK = True
    OPENSTACK_MAX_VM_COUNT = 2
    OPENSTACK_PRELOADED = {}

    OPENSTACK_AUTH_URL = "localhost"
    OPENSTACK_PORT = 5000
    OPENSTACK_CLIENT_VERSION = "v3"
    OPENSTACK_USERNAME = "user"
    OPENSTACK_PASSWORD = "password"
    OPENSTACK_TENANT_NAME = "name"
    OPENSTACK_TENANT_ID = "id"
    OPENSTACK_NETWORK_ID = "id"
    OPENSTACK_NETWORK_NAME = "network"
    OPENSTACK_ZONE_FOR_VM_CREATE = ""
    OPENSTACK_PLATFORM_NAME_PREFIX = "test_"
    OPENSTACK_DEFAULT_FLAVOR = 'flavor'
    OPENSTACK_DOMAIN_NAME = "test"
    OPENASTACK_VM_META_DATA = {
        'admin_pass': 'password'
    }
    OPENSTACK_VM_USERDATA_FILE_PATH = "%s/userdata" % os.path.abspath(os.curdir)

    USE_DOCKER = False
    BIND_LOCALHOST_PORTS = False
    DOCKER_MAX_COUNT = 3
    DOCKER_PRELOADED = {}
    DOCKER_BASE_URL = 'unix://var/run/docker.sock'
    DOCKER_TIMEOUT = 120
    DOCKER_NUM_POOLS = 100
    DOCKER_NETWORK_NAME = "vmmaster_network"
    DOCKER_SUBNET = "192.168.1.0/24"
    DOCKER_GATEWAY = "192.168.1.254"
    DOCKER_CONTAINER_MEMORY_LIMIT = "1g"
    DOCKER_CONTAINER_CPU_PERIOD = 100000
    DOCKER_CONTAINER_CPU_QUOTA = 50000
    DNS_LIST = []
    DNS_SEARCH_LIST = [
        "test"
    ]

    VM_PING_RETRY_COUNT = 3
    VM_CREATE_CHECK_PAUSE = 3
    VM_CREATE_CHECK_ATTEMPTS = 5
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 5
    PING_TIMEOUT = 5

    # vm pool
    GET_VM_TIMEOUT = 5
    SCREENCAST_RESOLUTION = (1600, 1200)
    MAKE_REQUEST_ATTEMPTS_AMOUNT = 5

    # selenium
    SELENIUM_PORT = 4455
    VMMASTER_AGENT_PORT = 9000
    VNC_PORT = 5900
    PORTS = [SELENIUM_PORT, VMMASTER_AGENT_PORT, VNC_PORT]

    THREAD_POOL_MAX = 100
    WAIT_ACTIVE_SESSIONS = False

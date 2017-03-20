import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9001

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/logs"
    LOG_SIZE = 5242880

    SCREENSHOTS_DIR = BASE_DIR + "/screenshots"

    # clones related stuff
    ORIGIN_POSTFIX = "origin"

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
        # 'origin_1': 1,
    }

    OPENSTACK_AUTH_URL = "localhost"
    OPENSTACK_PORT = 5000
    OPENSTACK_CLIENT_VERSION = "v2.0"
    OPENSTACK_USERNAME = "user"
    OPENSTACK_PASSWORD = "password"
    OPENSTACK_TENANT_NAME = "test"
    OPENSTACK_TENANT_ID = "id"
    OPENSTACK_NETWORK_ID = "id"
    OPENSTACK_ZONE_FOR_VM_CREATE = "zone"
    OPENSTACK_PLATFORM_NAME_PREFIX = "test_"
    OPENASTACK_VM_META_DATA = {
        'admin_pass': 'testPassw0rd.'
    }

    USE_DOCKER = False
    BIND_LOCALHOST_PORTS = False
    DOCKER_MAX_COUNT = 1
    DOCKER_PRELOADED = {}
    DOCKER_BASE_URL = 'unix://var/run/docker.sock'
    DOCKER_TIMEOUT = 120
    DOCKER_NUM_POOLS = 100
    DOCKER_NETWORK_NAME = "vmmaster_network"
    DOCKER_SUBNET = "192.168.0.0/24"
    DOCKER_GATEWAY = "192.168.0.254"
    DOCKER_CONTAINER_MEMORY_LIMIT = "1g"
    DOCKER_CONTAINER_CPU_PERIOD = 100000
    DOCKER_CONTAINER_CPU_QUOTA = 50000
    DNS_LIST = [
        "192.168.0.1",
    ]
    DNS_SEARCH_LIST = [
        "test",
    ]

    VM_CHECK = False
    VM_CHECK_FREQUENCY = 1800
    VM_PING_RETRY_COUNT = 1
    VM_CREATE_CHECK_PAUSE = 5
    VM_CREATE_CHECK_ATTEMPTS = 1000
    PRELOADER_FREQUENCY = 3
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    # vm pool
    GET_VM_TIMEOUT = 1
    GET_ENDPOINT_ATTEMPTS = 1
    GET_ENDPOINT_WAIT_TIME_INCREMENT = 0.01
    SCREENCAST_RESOLUTION = (1600, 1200)

    # GRAPHITE = ('graphite', 2003)

    SELENIUM_PORT = 4455
    VMMASTER_AGENT_PORT = 9000
    VNC_PORT = 5900
    PORTS = [SELENIUM_PORT, VMMASTER_AGENT_PORT, VNC_PORT]

    THREAD_POOL_MAX = 100

    LOG_LEVEL = "INFO"

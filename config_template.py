import os
from envparse import env
from os.path import isfile


if isfile('.env'):
    env.read_envfile('.env')


class Config(object):
    BASEDIR = env.str("BASEDIR", default=os.path.dirname(os.path.realpath(__file__)))
    PORT = env.int("PORT", default=9001)
    NO_SHUTDOWN_WITH_SESSIONS = env.bool("NO_SHUTDOWN_WITH_SESSIONS", default=False)
    ENDPOINT_THREADPOOL_PROCESSES = env.int("ENDPOINT_THREADPOOL_PROCESSES", default=1)

    # PostgreSQL dbname
    DATABASE = env.str("DATABASE", default="postgresql+psycopg2://vmmaster:vmmaster@localhost/testdb")

    # screenshots
    SCREENSHOTS_DIR = env.str("SCREENSHOTS_DIR", default=os.sep.join([BASEDIR, "screenshots"]))
    SCREENSHOTS_DAYS = env.int("SCREENSHOTS_DAYS", default=7)

    # logging
    LOG_TYPE = env.str("LOG_TYPE", default="logstash")
    LOG_LEVEL = env.str("LOG_LEVEL", default="DEBUG")

    # openstack
    USE_OPENSTACK = env.bool("USE_OPENSTACK", default=False)
    OPENSTACK_MAX_VM_COUNT = env.int("OPENSTACK_MAX_VM_COUNT", default=1)
    OPENSTACK_ENDPOINT_PREFIX = env.str("OPENSTACK_ENDPOINT_PREFIX", default="noprefix")
    OPENSTACK_PRELOADED = env.json("OPENSTACK_PRELOADED", default={})

    """
    Platforms settings

    Allowed platforms: ANDROID, LINUX, UNIX, MAC, WINDOWS, XP, VISTA
    Allowed browserNames: android, chrome, firefox, htmlunit, internet explorer, iPhone, iPad, opera, safari
    (source: https://github.com/SeleniumHQ/selenium/wiki/DesiredCapabilities)

    Example:
    PLATFORMS = {
        "LINUX": {
            "ubuntu-14.04": {
                "browsers": {
                    "chrome": "48",
                    "firefox": "25"
                }
            },
            "ubuntu-16.04": {
                "browsers": {
                    "chrome": "48",
                    "firefox": "25"
                }
            }
        },
        "WINDOWS": {
            "windows-8": {
                "browsers": {
                    "internet explorer": "9"
                }
            }
        },
        "MAC": {},
        "ANDROID": {}
    }
    """

    PLATFORMS = {
        "LINUX": {},
        "MAC": {},
        "WINDOWS": {},
        "ANDROID": {},
    }

    OPENSTACK_AUTH_URL = env.str("OPENSTACK_AUTH_URL", default="localhost")
    OPENSTACK_PORT = env.int("OPENSTACK_PORT", default=5000)
    OPENSTACK_CLIENT_VERSION = env.str("OPENSTACK_CLIENT_VERSION", default="v3")
    OPENSTACK_USERNAME = env.str("OPENSTACK_USERNAME", default="user")
    OPENSTACK_PASSWORD = env.str("OPENSTACK_PASSWORD", default="password")
    OPENSTACK_TENANT_NAME = env.str("OPENSTACK_TENANT_NAME", default="test")
    OPENSTACK_TENANT_ID = env.str("OPENSTACK_TENANT_ID", default="")
    OPENSTACK_ZONE_FOR_VM_CREATE = env.str("OPENSTACK_ZONE_FOR_VM_CREATE", default="")
    OPENSTACK_PLATFORM_NAME_PREFIX = env.str("OPENSTACK_PLATFORM_NAME_PREFIX", default="origin-")
    OPENSTACK_DEFAULT_FLAVOR = env.str("OPENSTACK_DEFAULT_FLAVOR", default='')
    OPENSTACK_NETWORK_ID = env.str("OPENSTACK_NETWORK_ID", default='')
    OPENSTACK_NETWORK_NAME = env.str("OPENSTACK_NETWORK_NAME", default='')
    OPENSTACK_DOMAIN_NAME = env.str("OPENSTACK_DOMAIN_NAME", default='')
    OPENASTACK_VM_META_DATA = env.json("OPENASTACK_VM_META_DATA", default={
        'admin_pass': 'testPassw0rd.'
    })

    # docker
    USE_DOCKER = env.bool("USE_DOCKER", default=False)
    BIND_LOCALHOST_PORTS = env.bool("BIND_LOCALHOST_PORTS", default=True)
    DOCKER_MAX_COUNT = env.int("DOCKER_MAX_COUNT", default=3)
    DOCKER_PRELOADED = env.json("DOCKER_PRELOADED", default={})
    DOCKER_BASE_URL = env.str("DOCKER_BASE_URL", default='unix://var/run/docker.sock')
    DOCKER_TIMEOUT = env.int("DOCKER_TIMEOUT", default=120)
    DOCKER_NUM_POOLS = env.int("DOCKER_NUM_POOLS", default=100)
    DOCKER_NETWORK_NAME = env.str("DOCKER_NETWORK_NAME", default="vmmaster_network")
    DOCKER_SUBNET = env.str("DOCKER_SUBNET", default="192.168.1.0/24")
    DOCKER_GATEWAY = env.str("DOCKER_GATEWAY", default="192.168.1.254")
    DOCKER_CONTAINER_MEMORY_LIMIT = env.str("DOCKER_CONTAINER_MEMORY_LIMIT", default="1g")
    DOCKER_CONTAINER_CPU_PERIOD = env.int("DOCKER_CONTAINER_CPU_PERIOD", default=100000)
    DOCKER_CONTAINER_CPU_QUOTA = env.int("DOCKER_CONTAINER_CPU_QUOTA", default=50000)
    DNS_LIST = env.list("DNS_LIST", default=[])
    DNS_SEARCH_LIST = env.list("DNS_SEARCH_LIST", default=[])

    VM_PING_RETRY_COUNT = env.int("VM_PING_RETRY_COUNT", default=3)
    VM_CREATE_CHECK_PAUSE = env.int("VM_CREATE_CHECK_PAUSE", default=5)
    VM_CREATE_CHECK_ATTEMPTS = env.int("VM_CREATE_CHECK_ATTEMPTS", default=1000)
    PRELOADER_FREQUENCY = env.int("PRELOADER_FREQUENCY", default=3)
    SESSION_TIMEOUT = env.int("SESSION_TIMEOUT", default=360)
    PING_TIMEOUT = env.int("PING_TIMEOUT", default=180)

    # vm pool
    GET_VM_TIMEOUT = env.int("GET_VM_TIMEOUT", default=180)
    SCREENCAST_RESOLUTION = env.tuple("SCREENCAST_RESOLUTION", default=(800, 600))
    MAKE_REQUEST_ATTEMPTS_AMOUNT = env.int("MAKE_REQUEST_ATTEMPTS_AMOUNT", default=5)

    # selenium
    SELENIUM_PORT = env.int("SELENIUM_PORT", default=4455)
    VMMASTER_AGENT_PORT = env.int("VMMASTER_AGENT_PORT", default=9000)
    VNC_PORT = env.int("VNC_PORT", default=5900)
    PORTS = [SELENIUM_PORT, VMMASTER_AGENT_PORT, VNC_PORT]

    THREAD_POOL_MAX = env.int("THREAD_POOL_MAX", default=100)
    WAIT_ACTIVE_SESSIONS = env.bool("WAIT_ACTIVE_SESSIONS", default=False)

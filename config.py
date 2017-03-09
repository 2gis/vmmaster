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

    CLONES_DIR = env.str("CLONES_DIR", default=os.sep.join([BASEDIR, "clones"]))
    ORIGINS_DIR = env.str("ORIGINS_DIR", default=os.sep.join([BASEDIR, "origins"]))
    SESSION_DIR = env.str("SESSION_DIR", default=os.sep.join([BASEDIR, "session"]))

    # screenshots
    SCREENSHOTS_DIR = env.str("SCREENSHOTS_DIR", default=os.sep.join([BASEDIR, "screenshots"]))
    SCREENSHOTS_DAYS = env.int("SCREENSHOTS_DAYS", default=7)

    # logging
    LOG_TYPE = env.str("LOG_TYPE", default="logstash")
    LOG_LEVEL = env.str("LOG_LEVEL", default="DEBUG")

    # openstack
    USE_OPENSTACK = env.bool("USE_OPENSTACK", default=True)
    OPENSTACK_MAX_VM_COUNT = env.int("OPENSTACK_MAX_VM_COUNT", default=1)
    OPENSTACK_PRELOADED = env.json("OPENSTACK_PRELOADED", default={})

    OPENSTACK_AUTH_URL = env.str("OPENSTACK_AUTH_URL", default="localhost")
    OPENSTACK_PORT = env.int("OPENSTACK_PORT", default=5000)
    OPENSTACK_CLIENT_VERSION = env.str("OPENSTACK_CLIENT_VERSION", default="v2.0")
    OPENSTACK_USERNAME = env.str("OPENSTACK_USERNAME", default="user")
    OPENSTACK_PASSWORD = env.str("OPENSTACK_PASSWORD", default="password")
    OPENSTACK_TENANT_NAME = env.str("OPENSTACK_TENANT_NAME", default="test")
    OPENSTACK_TENANT_ID = env.str("OPENSTACK_TENANT_ID", default="")
    OPENSTACK_ZONE_FOR_VM_CREATE = env.str("OPENSTACK_ZONE_FOR_VM_CREATE", default="")
    OPENSTACK_PLATFORM_NAME_PREFIX = env.str("OPENSTACK_PLATFORM_NAME_PREFIX", default="origin-")
    OPENSTACK_PING_RETRY_COUNT = env.int("OPENSTACK_PING_RETRY_COUNT", default=3)
    OPENSTACK_DEFAULT_FLAVOR = env.str("OPENSTACK_DEFAULT_FLAVOR", default='')
    OPENASTACK_VM_META_DATA = env.json("OPENASTACK_VM_META_DATA", default={
        'admin_pass': 'testPassw0rd.'
    })

    VM_CREATE_CHECK_PAUSE = env.int("VM_CREATE_CHECK_PAUSE", default=5)
    VM_CREATE_CHECK_ATTEMPTS = env.int("VM_CREATE_CHECK_ATTEMPTS", default=1000)
    PRELOADER_FREQUENCY = env.int("PRELOADER_FREQUENCY", default=3)
    SESSION_TIMEOUT = env.int("SESSION_TIMEOUT", default=360)
    PING_TIMEOUT = env.int("PING_TIMEOUT", default=180)

    # vm pool
    GET_VM_TIMEOUT = env.int("GET_VM_TIMEOUT", default=180)

    # selenium
    SELENIUM_PORT = env.int("SELENIUM_PORT", default=4455)
    VMMASTER_AGENT_PORT = env.int("VMMASTER_AGENT_PORT", default=9000)

    THREAD_POOL_MAX = env.int("THREAD_POOL_MAX", default=100)

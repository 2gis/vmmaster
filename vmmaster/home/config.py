import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9000
    DATABASE = "sqlite:///" + BASE_DIR + "/vmmaster.db"

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/log"

    # clones related stuff
    MAX_CLONE_COUNT = 2
    CLONE_TIMEOUT = 360
    PING_TIMEOUT = 180

    # additional logging
    # GRAYLOG = ('logserver', 12201)

    # selenium
    SELENIUM_PORT = "4455"

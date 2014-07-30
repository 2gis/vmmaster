import os


class Config(object):
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
    PORT = 9000
    DATABASE = "sqlite:///" + BASEDIR + "/vmmaster.db"

    CLONES_DIR = BASEDIR + "/clones"
    ORIGINS_DIR = BASEDIR + "/origins"
    SESSION_DIR = BASEDIR + "/session"

    # screenshots
    SCREENSHOTS_DIR = BASEDIR + "/screenshots"
    SCREENSHOTS_DAYS = 7

    # logging
    LOG_DIR = BASEDIR + "/log"
    LOG_SIZE = 5242880

    # vm related stuff
    MAX_VM_COUNT = 2
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    # additional logging
    # GRAYLOG = ('logserver', 12201)

    # selenium
    SELENIUM_PORT = "4455"

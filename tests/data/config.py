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
    MAX_VM_COUNT = 2
    SESSION_TIMEOUT = 360
    PING_TIMEOUT = 180

    GRAPHITE = ('graphite', 2003)

    SELENIUM_PORT = "4455"

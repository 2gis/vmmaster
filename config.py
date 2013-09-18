class Config:
    #BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = "/home/vmmaster/vmmaster"
    PORT = 9000

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/log"

    # clones related stuff
    ORIGIN_POSTFIX = "origin"
    MAX_CLONE_COUNT = 2
    CLONE_TIMEOUT = 360
    PING_TIMEOUT = 180

    SELENIUM_PORT = "4455"

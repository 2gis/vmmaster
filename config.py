import os


class Config:
    #BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = "/home/vmmaster/vmmaster"

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/log"

    ORIGIN_POSTFIX = "origin"

    SELENIUM_PORT = "4455"

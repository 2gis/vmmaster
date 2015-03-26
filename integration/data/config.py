import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

    DATABASE = "postgresql+psycopg2://vmmaster:vmmaster@localhost/test"

    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"
    LOG_DIR = BASE_DIR + "/log"

    SCREENSHOTS_DIR = BASE_DIR + "/screenshots"
    SCREENSHOTS_DAYS = 7
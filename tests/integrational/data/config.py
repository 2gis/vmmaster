import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

    DATABASE = "postgresql+psycopg2://vmmaster:vmmaster@localhost/vmmaster_db"

    CLONES_DIR = BASE_DIR + "/vmmaster/clones"
    ORIGINS_DIR = BASE_DIR + "/vmmaster/origins"
    SESSION_DIR = BASE_DIR + "/vmmaster/session"
    LOG_DIR = BASE_DIR + "/logs"

    SCREENSHOTS_DIR = BASE_DIR + "/vmmaster/screenshots"
    SCREENSHOTS_DAYS = 7

    LOG_LEVEL = "INFO"
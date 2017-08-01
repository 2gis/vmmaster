import os


class Config(object):
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

    DATABASE = "postgresql+psycopg2://vmmaster:vmmaster@localhost/vmmaster_db"

    LOG_DIR = BASE_DIR + "/logs"
    LOG_SIZE = 5242880

    SCREENSHOTS_DIR = BASE_DIR + "/screenshots"
    SCREENSHOTS_DAYS = 7

    LOG_LEVEL = "INFO"

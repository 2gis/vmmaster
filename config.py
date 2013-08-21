import os


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # relative to BASE_DIR
    CLONES_DIR = BASE_DIR + "/clones"
    ORIGINS_DIR = BASE_DIR + "/origins"
    SESSION_DIR = BASE_DIR + "/session"

    ORIGIN_POSTFIX = "origin"

    selenium_port = "4455"
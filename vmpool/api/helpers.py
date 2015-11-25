# coding: utf-8

from vmpool.platforms import Platforms
from vmpool.virtual_machines_pool import pool


def get_platforms():
    return Platforms.info()


def get_pool():
    return pool.info

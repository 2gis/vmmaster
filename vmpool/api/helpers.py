# coding: utf-8

from flask import current_app


def get_platforms():
    return current_app.pool.platforms.info()


def get_pool():
    return current_app.pool.info

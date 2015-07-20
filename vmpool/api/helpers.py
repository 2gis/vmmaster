# coding: utf-8
from flask import jsonify

from vmpool.platforms import Platforms
from vmpool.virtual_machines_pool import pool


def get_platforms():
    return Platforms.info()


def get_pool():
    return pool.info


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)
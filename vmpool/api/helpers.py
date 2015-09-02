# coding: utf-8

from flask import jsonify

from vmpool.platforms import Platforms
from vmpool.virtual_machines_pool import pool
from vmpool.vmqueue import q


def get_platforms():
    return Platforms.info()


def get_pool():
    pool_info = pool.info
    pool_info['pool_queue'] = q.info
    return pool_info


def get_queue():
    return q.info


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)
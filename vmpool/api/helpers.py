# coding: utf-8

from flask import current_app


def get_platforms():
    return current_app.pool.platforms.info()


def get_pool():
    return current_app.pool.info


def get_artifact_collector_queue():
    return current_app.pool.artifact_collector.get_queue()


def get_node_info():
    return current_app.id

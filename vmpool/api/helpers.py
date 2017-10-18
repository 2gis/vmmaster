# coding: utf-8

from flask import current_app


def get_platforms():
    return current_app.pool.platforms.info()


def get_pool():
    return current_app.pool.info


def get_artifact_collector_queue():
    return current_app.pool.artifact_collector.get_queue()


def get_provider_info():
    return {
        "name": current_app.pool.name,
        "config": current_app.pool.provider.config
    }


def get_endpoint_by_name(endpoint_name):
    return current_app.pool.get_by_name(endpoint_name)


def get_active_sessions():
    return current_app.pool.active_endpoints

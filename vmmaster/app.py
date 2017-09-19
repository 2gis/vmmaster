# coding: utf-8

import logging
from uuid import uuid1
from flask import json, Flask
from core.config import config

log = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class Vmmaster(Flask):
    def __init__(self, *args, **kwargs):
        from core.db import Database
        from core.sessions import Sessions
        from vmpool.virtual_machines_pool import VirtualMachinesPool

        super(Vmmaster, self).__init__(*args, **kwargs)
        self.running = True
        self.uuid = str(uuid1())
        self.database = Database()
        self.pool = VirtualMachinesPool(self)
        self.sessions = Sessions(self)
        self.json_encoder = JSONEncoder

        self.pool.start_workers()
        self.sessions.start_workers()

    def cleanup(self):
        log.info("Cleanup...")
        try:
            self.pool.stop_workers()
            self.sessions.stop_workers()
            log.info("Cleanup done")
        except:
            log.exception("Cleanup was finished with errors")

    def match(self, dc):
        return self.pool.matcher.match(dc)


def register_blueprints(app):
    from api import api
    from webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")

    app = Vmmaster(__name__)

    register_blueprints(app)
    return app

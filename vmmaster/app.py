# coding: utf-8

from flask import Flask
from flask.json import JSONEncoder as FlaskJSONEncoder
from uuid import uuid1
from core.logger import log
from core.config import config


class JSONEncoder(FlaskJSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class Vmmaster(Flask):
    def __init__(self, *args, **kwargs):
        super(Vmmaster, self).__init__(*args, **kwargs)
        self.running = True
        self.uuid = str(uuid1())

        from core.db import Database
        self.database = Database()

        from vmpool.virtual_machines_pool import VirtualMachinesPool
        self.pool = VirtualMachinesPool()

        from core.sessions import Sessions
        self.sessions = Sessions(self)

        self.json_encoder = JSONEncoder

        self.register()

    def register(self):
        self.database.register_platforms(self.uuid, self.pool.platforms.info())

    def unregister(self):
        self.database.unregister_platforms(self.uuid)

    def cleanup(self):
        log.info("Shutting down...")
        self.pool.preloader.stop()
        self.sessions.worker.stop()
        self.pool.free()
        self.unregister()
        self.pool.platforms.cleanup()

        log.info("Server gracefully shut down.")


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

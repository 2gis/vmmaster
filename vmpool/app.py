# coding: utf-8

import logging
from flask import json, Flask
from core.config import config

log = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class VMPool(Flask):
    id = None

    def __init__(self, *args, **kwargs):
        from core.db import Database
        from core.sessions import Sessions
        from vmpool.virtual_machines_pool import VirtualMachinesPool

        super(VMPool, self).__init__(*args, **kwargs)
        self.running = True
        self.database = Database()
        self.sessions = Sessions(self)
        self.pool = VirtualMachinesPool(self)
        self.json_encoder = JSONEncoder
        self.id = self.register()
        self.pool.start_workers()
        log.info("Provider #%s was started..." % self.id)

    def register(self):
        return self.database.register_provider(
            name="Unnamed provider",
            url="%s:%s" % ("localhost", config.PORT),
            platforms=self.pool.platforms.info()
        )

    def unregister(self):
        self.database.unregister_provider(self.id)

    def cleanup(self):
        log.info("Shutting down...")
        self.pool.stop_workers()
        self.pool.free()
        self.unregister()
        self.pool.platforms.cleanup()
        log.info("Server gracefully shut down.")


def register_blueprints(app):
    from vmpool.api import api
    app.register_blueprint(api, url_prefix='/api')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")

    app = VMPool(__name__)

    register_blueprints(app)
    return app

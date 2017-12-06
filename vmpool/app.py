# coding: utf-8

import logging
from flask import Flask
from core.config import config
from core.utils import JSONEncoder

log = logging.getLogger(__name__)


class Provider(Flask):
    def __init__(self, *args, **kwargs):
        from core.db import Database
        from core.sessions import Sessions
        from vmpool.virtual_machines_pool import VirtualMachinesPool

        super(Provider, self).__init__(*args, **kwargs)
        self.running = True
        self.json_encoder = JSONEncoder
        self.database = Database()
        self.sessions = Sessions(self.database, self.app_context)
        self.pool = VirtualMachinesPool(app=self, name=config.PROVIDER_NAME)
        self.pool.start_workers()

    def cleanup(self):
        try:
            log.info("Cleanup...")
            self.pool.stop_workers()
            log.info("Cleanup was done")
        except:
            log.exception("Cleanup was finished with errors")

    def stop(self):
        self.running = False


def register_blueprints(app):
    from vmpool.api import api
    app.register_blueprint(api, url_prefix='/api')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")

    app = Provider(__name__)

    register_blueprints(app)
    return app

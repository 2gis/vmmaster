# coding: utf-8

from flask import Flask
from flask.json import JSONEncoder as FlaskJSONEncoder
from uuid import uuid1

from core.sessions import Sessions, SessionWorker
from core.logger import log

from core.db import database

from vmpool.platforms import Platforms

from vmpool.virtual_machines_pool import pool, \
    VirtualMachinesPoolPreloader

from vmpool.vmqueue import q, QueueWorker

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

        self.database = database
        self.pool = pool
        self.platforms = Platforms()
        self.queue = q

        self.preloader = VirtualMachinesPoolPreloader(self.pool)
        self.preloader.start()

        self.worker = QueueWorker(self.queue)
        self.worker.start()

        self.sessions = Sessions()

        self.session_worker = SessionWorker(app=self)
        self.session_worker.start()

        self.json_encoder = JSONEncoder

        self.register()

    def register(self):
        self.database.register_platforms(self.uuid, self.platforms.info())

    def unregister(self):
        self.database.unregister_platforms(self.uuid)

    def cleanup(self):
        log.info("Shutting down...")
        self.worker.stop()
        self.preloader.stop()
        self.session_worker.stop()
        self.pool.free()
        self.unregister()
        self.platforms.cleanup()
        log.info("Server gracefully shut down.")


def register_blueprints(app):
    from api import api
    from webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")
    if database is None:
        raise Exception("Need to setup database")

    app = Vmmaster(__name__)

    register_blueprints(app)
    return app

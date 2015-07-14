from flask import Flask
from flask.json import JSONEncoder as FlaskJSONEncoder
from core.platforms import Platforms
from core.sessions import Sessions
from core.network.network import Network
from core.session_queue import q
from core.virtual_machine.virtual_machines_pool import \
    VirtualMachinesPoolPreloader, pool, VirtualMachineChecker
from core.logger import log


class JSONEncoder(FlaskJSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class vmmaster(Flask):
    def __init__(self, *args, **kwargs):
        super(vmmaster, self).__init__(*args, **kwargs)
        self.running = True

        self.network = Network()

        self.json_encoder = JSONEncoder
        self.platforms = Platforms()
        self.queue = q
        self.sessions = Sessions()

        self.preloader = VirtualMachinesPoolPreloader(pool)
        self.preloader.start()
        self.vmchecker = VirtualMachineChecker(pool)
        self.vmchecker.start()

    def cleanup(self):
        log.info("Shutting down...")
        self.preloader.stop()
        self.vmchecker.stop()
        pool.free()
        self.network.delete()
        log.info("Server gracefully shut down.")


def register_blueprints(app):
    from api import api
    from webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    from core.config import config
    from core.db import database

    if config is None:
        raise Exception("Need to setup config.py in application directory")
    if database is None:
        raise Exception("Need to setup database")

    app = vmmaster(__name__)

    register_blueprints(app)
    return app
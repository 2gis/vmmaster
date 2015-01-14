import atexit

# make a Flask app
from flask import Flask
from flask.json import JSONEncoder as FlaskJSONEncoder

# run in twisted wsgi
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site

from .core.platforms import Platforms
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log

from .core.session_queue import QueueWorker, q
from .core.virtual_machine.virtual_machines_pool import VirtualMachinesPoolPreloader, pool


class JSONEncoder(FlaskJSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


def register_blueprints(app):
    from api import api
    from webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    from .core.config import config
    from .core.db import database
    if config is None:
        raise Exception("Need to setup config")
    if database is None:
        raise Exception("Need to setup database")

    network = Network()
    sessions = Sessions()
    platforms = Platforms()

    app = Flask(__name__)
    app.json_encoder = JSONEncoder
    app.platforms = platforms
    app.queue = q
    app.sessions = sessions

    preloader = VirtualMachinesPoolPreloader(pool)
    preloader.start()
    worker = QueueWorker(q)
    worker.start()

    atexit.register(shut_down_routine, functions_array=[
        # order matters
        (log.info, "Shutting down..."),
        worker.stop,
        preloader.stop,
        pool.free,
        sessions.delete,
        network.delete,
        (log.info, "Server gracefully shut down.")])

    # platform_handler = PlatformHandler(sessions)
    # app.add_url_rule("/wd/hub/<path:path>", methods=['GET', 'POST', 'DELETE'],
    #                  endpoint='platform_handler', view_func=platform_handler)
    register_blueprints(app)
    return app


def shut_down_routine(functions_array):
    for function in functions_array:
        if hasattr(function, '__len__') and len(function) > 1:
            function[0](*function[1:])
        else:
            function()


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        app = create_app()
        resource = WSGIResource(self.reactor, self.reactor.getThreadPool(), app)
        site = Site(resource)

        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.run()
        del self
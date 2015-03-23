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
from .core.virtual_machine.virtual_machines_pool import VirtualMachinesPoolPreloader, pool, VirtualMachineChecker


class JSONEncoder(FlaskJSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class vmmaster(Flask):
    def __init__(self, *args, **kwargs):
        super(vmmaster, self).__init__(*args, **kwargs)

        self.network = Network()
        sessions = Sessions()
        platforms = Platforms()

        self.json_encoder = JSONEncoder
        self.platforms = platforms
        self.queue = q
        self.sessions = sessions

        self.preloader = VirtualMachinesPoolPreloader(pool)
        self.preloader.start()
        self.vmchecker = VirtualMachineChecker(pool)
        self.vmchecker.start()
        self.worker = QueueWorker(q)
        self.worker.start()

    def cleanup(self):
        log.info("Shutting down...")
        self.worker.stop()
        self.preloader.stop()
        self.vmchecker.stop()
        self.sessions.delete()
        pool.free()
        self.network.delete()
        log.info("Server gracefully shut down.")


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

    app = vmmaster(__name__)

    register_blueprints(app)
    return app


def _block_on(d, timeout=None):
    from Queue import Queue, Empty
    from twisted.internet.defer import TimeoutError
    from twisted.python.failure import Failure
    from twisted.internet.defer import Deferred
    q = Queue()
    if not isinstance(d, Deferred):
        return None
    d.addBoth(q.put)
    try:
        ret = q.get(timeout is not None, timeout)
    except Empty:
        raise TimeoutError
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.app = create_app()
        resource = WSGIResource(self.reactor, self.reactor.getThreadPool(), self.app)
        site = Site(resource)

        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.run()
        del self

    def __del__(self):
        d = self.bind.stopListening()
        _block_on(d, 20)
        self.app.cleanup()
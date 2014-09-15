# make a Flask app
from flask import Flask
# run in under twisted through wsgi
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.internet.defer import Deferred

from .core.platforms import Platforms
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log
from .core.platform_server import PlatformHandler
from .core.api import ApiHandler
from .core.session_queue import QueueWorker, q
from .core.virtual_machine.virtual_machines_pool import VirtualMachinesPreloader, pool


def _block_on(d, timeout=None):
    from Queue import Queue, Empty
    from twisted.internet.defer import TimeoutError
    from twisted.python.failure import Failure
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
        from .core.config import config
        from .core.db import database
        if config is None:
            raise Exception("Need to setup config")
        if database is None:
            raise Exception("Need to setup database")

        self.reactor = reactor
        self.network = Network()
        self.sessions = Sessions()
        self.platforms = Platforms()
        self.worker = QueueWorker(q)
        self.worker.start()
        self.preloader = VirtualMachinesPreloader()
        self.preloader.start()

        app = Flask(__name__)
        platform_handler = PlatformHandler(self.sessions)
        api_handler = ApiHandler(self.sessions)
        app.add_url_rule("/wd/hub/<path:path>", methods=['GET', 'POST', 'DELETE'],
                         endpoint='platform_handler', view_func=platform_handler)
        app.add_url_rule("/api/sessions", methods=['GET'], view_func=api_handler.sessions)
        app.add_url_rule("/api/platforms", methods=['GET'], view_func=api_handler.platforms)
        app.add_url_rule("/api/queue", methods=['GET'], view_func=api_handler.queue)
        app.add_url_rule("/api/session/<id>/stop", methods=['POST'], view_func=api_handler.stop_session)
        resource = WSGIResource(reactor, reactor.getThreadPool(), app)
        site = Site(resource)

        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def __del__(self):
        log.info("shutting down...")
        d = self.bind.stopListening()
        _block_on(d, 20)
        self.preloader.stop()
        self.worker.stop()
        pool.free()
        self.sessions.delete()
        self.network.delete()
        log.info("Server gracefully shut down.")

    def run(self):
        self.reactor.run()
        del self
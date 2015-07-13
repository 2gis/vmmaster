# coding: utf-8

# make a Flask app
from flask import Flask
from flask.json import JSONEncoder as FlaskJSONEncoder

# run in twisted wsgi
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site, NOT_DONE_YET
from twisted.internet import defer

from .core.platforms import Platforms
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log

from .core.virtual_machine.virtual_machines_pool import \
    VirtualMachinesPoolPreloader, pool, VirtualMachineChecker


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
        sessions = Sessions()
        platforms = Platforms()

        self.json_encoder = JSONEncoder
        self.platforms = platforms
        self.sessions = sessions

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
    _q = Queue()
    if not isinstance(d, Deferred):
        return None
    d.addBoth(_q.put)
    try:
        ret = _q.get(timeout is not None, timeout)
    except Empty:
        raise TimeoutError
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret


class VmmasterResource(WSGIResource):
    isLeaf = True
    waiting_requests = []

    def notify_no_more_waiting(self):
        if not self.waiting_requests:
            return defer.succeed(None)
        deffered_list = defer.gatherResults(self.waiting_requests,
                                            consumeErrors=True)
        log.info("Waiting for end %s request[s]." %
                 len(deffered_list._deferredList))
        return deffered_list.addBoth(lambda ign: None)

    def render(self, request):
        super(VmmasterResource, self).render(request)
        d = request.notifyFinish()
        self.waiting_requests.append(d)
        d.addBoth(lambda ign: self.waiting_requests.remove(d))

        return NOT_DONE_YET


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.app = create_app()
        self.resource = VmmasterResource(self.reactor,
                                         self.reactor.getThreadPool(),
                                         self.app)
        site = Site(self.resource)
        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.addSystemEventTrigger('before', 'shutdown',
                                           self.before_shutdown)
        self.reactor.run()
        del self

    def __del__(self):
        d = self.bind.stopListening()
        _block_on(d, 20)
        self.app.cleanup()

    def wait_for_writers(self):
        d = defer.Deferred()

        def check_writers(self):
            if len(self.reactor.getWriters()) > 0:
                self.reactor.callLater(0.1, check_writers, self)
            else:
                d.callback(None)

        check_writers(self)

        return d

    @defer.inlineCallbacks
    def before_shutdown(self):
        self.app.running = False
        yield self.resource.notify_no_more_waiting()
        yield self.wait_for_writers()
        log.info("All active requests has been completed.")

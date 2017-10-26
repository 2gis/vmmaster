# coding: utf-8

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.python.threadpool import ThreadPool
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from prometheus_client.twisted import MetricsResource

from vmpool.app import create_app
from core.logger import log
from core.config import config
from core.utils import RootResource


class ProviderServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.reactor.addSystemEventTrigger('before', 'shutdown', self.before_shutdown)
        self.reactor.suggestThreadPoolSize(config.REACTOR_THREAD_POOL_MAX)
        self.app = create_app()
        self.thread_pool = ThreadPool(maxthreads=config.FLASK_THREAD_POOL_MAX)
        self.thread_pool.start()
        wsgi_resource = WSGIResource(self.reactor, self.thread_pool, self.app)

        root_resource = RootResource(wsgi_resource)
        root_resource.putChild("metrics", MetricsResource())
        site = Site(root_resource)
        self.bind = self.reactor.listenTCP(port, site)
        log.info('Provider is listening on {} ...'.format(port))

    def run(self):
        self.reactor.run()

    def stop_services(self):
        log.info("Shutting down provider...")
        self.app.cleanup()
        self.thread_pool.stop()
        return maybeDeferred(self.bind.stopListening).addCallbacks(
            callback=lambda _: log.info("Port listening was stopped"),
            errback=lambda failure: log.error("Error while stopping port listening: {}".format(failure))
        )

    @inlineCallbacks
    def before_shutdown(self):
        self.app.stop()
        yield self.stop_services()

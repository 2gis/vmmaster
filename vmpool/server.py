# coding: utf-8

from Queue import Queue, Empty

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.python.failure import Failure
from twisted.python.threadpool import ThreadPool
from twisted.internet.defer import inlineCallbacks, Deferred, TimeoutError
from twisted.internet.threads import deferToThread

from vmpool.app import create_app
from core.logger import log
from core.config import config


def _block_on(d, timeout=None):
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


class RootResource(Resource):
    def __init__(self, fallback_resource):
        Resource.__init__(self)
        self.fallback_resource = fallback_resource

    def getChildWithDefault(self, path, request):
        if path in self.children:
            return self.children[path]

        request.postpath.insert(0, path)
        return self.fallback_resource


class VMPoolServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.reactor.addSystemEventTrigger('before', 'shutdown',
                                           self.before_shutdown)
        self.app = create_app()
        self.thread_pool = ThreadPool(maxthreads=config.THREAD_POOL_MAX)
        self.thread_pool.start()
        wsgi_resource = WSGIResource(self.reactor, self.thread_pool, self.app)

        root_resource = RootResource(wsgi_resource)
        site = Site(root_resource)
        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.run()

    def stop_services(self):
        # def lets_do_it():
        self.bind.stopListening()
        # _block_on(d, 20)
        self.app.cleanup()
        self.thread_pool.stop()

        # return deferToThread(lets_do_it).addBoth(
        #     lambda i: log.info('All services has been stopped')
        # )

    @inlineCallbacks
    def before_shutdown(self):
        self.app.running = False
        self.stop_services()
        yield deferToThread(lambda: None).addBoth(
            lambda i: log.info("All before shutdown tasks has been completed")
        )

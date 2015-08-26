# coding: utf-8

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site, NOT_DONE_YET
from twisted.internet import defer
from app import create_app

from core.logger import log


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

        def check_writers(_self):
            if len(_self.reactor.getWriters()) > 0:
                _self.reactor.callLater(0.1, check_writers, _self)
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

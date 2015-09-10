# coding: utf-8

import time
from twisted.internet.threads import deferToThread
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import defer
from app import create_app

from http_proxy import ProxyResource, HTTPChannelWithClient
from core.logger import log
from core.exceptions import SessionException


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


class RootResource(Resource):
    def __init__(self, fallback_resource):
        Resource.__init__(self)
        self.fallback_resource = fallback_resource

    def getChildWithDefault(self, path, request):
        if path in self.children:
            return self.children[path]

        request.postpath.insert(0, path)
        return self.fallback_resource


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.app = create_app()
        wsgi_resource = WSGIResource(self.reactor,
                                     self.reactor.getThreadPool(),
                                     self.app)
        root_resource = RootResource(wsgi_resource)
        root_resource.putChild("proxy", ProxyResource(self.app))
        site = Site(root_resource)
        site.protocol = HTTPChannelWithClient
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

    def wait_for_end_active_sessions(self):
        from core.db import database

        active_sessions = database.get_all_active_sessions()

        def wait_for(_self):
            while active_sessions:
                for session in active_sessions:
                    try:
                        _session = _self.app.sessions.get_session(session.id)
                    except SessionException:
                        _session = None
                    if _session:
                        if _session.status in ('failed', 'success'):
                            active_sessions.remove(session)
                    else:
                        active_sessions.remove(session)

                time.sleep(1)
                log.info("Wait for end %s session[s]" % len(active_sessions))

        return deferToThread(wait_for, self).addBoth(lambda i: None)

    @defer.inlineCallbacks
    def before_shutdown(self):
        self.app.running = False
        yield self.wait_for_end_active_sessions()
        log.info("All active sessions has been completed.")

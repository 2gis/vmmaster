# coding: utf-8

import time
import logging

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.python.threadpool import ThreadPool
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.internet.threads import deferToThread
from prometheus_client.twisted import MetricsResource

from app import create_app
from http_proxy import ProxyResource, HTTPChannelWithClient
from core.config import config

log = logging.getLogger(__name__)


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
        self.reactor.addSystemEventTrigger('before', 'shutdown', self.before_shutdown)
        self.reactor.addSystemEventTrigger('during', 'shutdown', self.during_shutdown)
        self.app = create_app()
        self.thread_pool = ThreadPool(maxthreads=config.THREAD_POOL_MAX)
        self.thread_pool.start()
        wsgi_resource = WSGIResource(self.reactor, self.thread_pool, self.app)

        root_resource = RootResource(wsgi_resource)
        root_resource.putChild("proxy", ProxyResource(self.app))
        root_resource.putChild("metrics", MetricsResource())
        site = Site(root_resource)
        site.protocol = HTTPChannelWithClient
        self.bind = self.reactor.listenTCP(port, site)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.run()

    def stop_services(self):
        log.info("Shutting down server...")
        self.app.cleanup()
        self.thread_pool.stop()
        log.info("Server gracefully shut down")
        return maybeDeferred(self.bind.stopListening).addCallbacks(
            callback=lambda _: log.info("Port listening was stopped"),
            errback=lambda failure: log.error("Error while stopping port listening: {}".format(failure))
        )

    def wait_for_end_active_sessions(self):
        active_sessions = self.app.sessions.active()

        def wait_for():
            while active_sessions:
                log.info("Waiting for {} sessions to complete: {}"
                         .format(len(active_sessions), [(i.id, i.status) for i in active_sessions]))
                for session in active_sessions:
                    if session.is_done:
                        log.debug("Session {} is done".format(session.id))
                        active_sessions.remove(session)

                time.sleep(1)

        return deferToThread(wait_for).addCallbacks(
            callback=lambda _: log.info("All active sessions has been completed"),
            errback=lambda failure: log.error("Error while waiting for active_sessions: {}".format(failure))
        )

    @inlineCallbacks
    def before_shutdown(self):
        self.app.running = False
        if getattr(config, 'WAIT_ACTIVE_SESSIONS', None):
            yield self.wait_for_end_active_sessions()

    @inlineCallbacks
    def during_shutdown(self):
        yield self.stop_services()

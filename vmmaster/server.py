# coding: utf-8

from time import sleep
import time
import logging

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.python.threadpool import ThreadPool
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.internet.threads import deferToThread
from prometheus_client.twisted import MetricsResource

from app import create_app
from http_proxy import ProxyResource, HTTPChannelWithClient
from core.config import config
from core.utils import RootResource

log = logging.getLogger(__name__)


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.reactor.addSystemEventTrigger('before', 'shutdown', self.before_shutdown)
        self.reactor.addSystemEventTrigger('during', 'shutdown', self.during_shutdown)
        self.reactor.addSystemEventTrigger('after', 'shutdown', lambda: log.info('after shutdown'))
        self.reactor.suggestThreadPoolSize(config.REACTOR_THREAD_POOL_MAX)

        self.app = create_app()
        self.wsgi_thread_pool = ThreadPool(maxthreads=config.FLASK_THREAD_POOL_MAX)
        self.wsgi_thread_pool.start()
        wsgi_resource = WSGIResource(self.reactor, self.wsgi_thread_pool, self.app)

        root_resource = RootResource(wsgi_resource)
        root_resource.putChild("proxy", ProxyResource(self.app))
        root_resource.putChild("metrics", MetricsResource())
        site = Site(root_resource)
        site.protocol = HTTPChannelWithClient
        self.bind = self.reactor.listenTCP(port, site)

        self._wait_for_end_active_sessions = getattr(config, 'WAIT_ACTIVE_SESSIONS', False)
        log.info('Server is listening on %s ...' % port)

    def run(self):
        self.reactor.run()

    def stop_services(self):
        log.info("Shutting down server...")
        # sleep(5)
        self.app.cleanup()
        # sleep(5)
        self.wsgi_thread_pool.stop()
        log.info("hey, client, you ok?")
        # sleep(5)
        return maybeDeferred(self.bind.stopListening).addCallbacks(
            callback=lambda _: log.info("Port listening was stopped"),
            errback=lambda failure: log.error("Error while stopping port listening: {}".format(failure))
        )

    def wait_for_end_active_sessions(self):
        def wait_for():
            with self.app.app_context():
                active_sessions = self.app.sessions.active()
                while active_sessions:
                    log.info("Waiting for {} sessions to complete: {}"
                             .format(len(active_sessions), [(i.id, i.status) for i in active_sessions]))
                    for session in active_sessions:
                        session.refresh()
                        if session.is_done:
                            log.debug("Session {} is done".format(session.id))
                            active_sessions.remove(session)

                    time.sleep(1)

        return deferToThread(wait_for).addCallbacks(
            callback=lambda _: log.info("All active sessions has been completed"),
            errback=lambda failure: log.error("Error while waiting for active_sessions: {}".format(failure))
        )

    def terminate_sessions(self):
        def interrupt():
            with self.app.app_context():
                for session in self.app.sessions.active():
                    session.failed(reason='Interrupted by server shut down')

        return deferToThread(interrupt).addCallbacks(
            callback=lambda _: log.info("Sessions terminated"),
            errback=lambda failure: log.error("Error while terminating sessions: {}".format(failure))
        )

    @inlineCallbacks
    def before_shutdown(self):
        log.info('before shutdown start')
        self.app.stop()
        log.info('TERMINATE')
        if self._wait_for_end_active_sessions:
            yield self.wait_for_end_active_sessions()
        else:
            yield self.terminate_sessions()
        log.info('before shutdown done')
        sleep(10)

    @inlineCallbacks
    def during_shutdown(self):
        log.info('during shutdown start')
        yield self.stop_services()
        log.info("Server gracefully shut down")
        log.info('during shutdown done')

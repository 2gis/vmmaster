# coding: utf-8

from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from core.logger import log
from vmpool.app import app


class VMPool(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.app = app()
        resource = WSGIResource(self.reactor,
                                self.reactor.getThreadPool(),
                                self.app)
        site = Site(resource)
        self.bind = self.reactor.listenTCP(port, site)
        log.info('VM Pool is listening on %s ...' % port)

    def run(self):
        self.reactor.run()

    def __del__(self):
        self.bind.stopListening()
        self.app.shutdown()

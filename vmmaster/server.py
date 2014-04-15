from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from .core.clone_factory import CloneFactory
from .core.network.sessions import Sessions
from .core.network.network import Network
from .core.logger import log
from .core.server.clone_server import ProxyFactory
from .core.server.api import ApiServer
from .core.db import Database
from .core.config import config


class VMMasterServer(object):
    def __init__(self, server_address):
        # creating network
        self.network = Network()
        self.clone_factory = CloneFactory()
        self.sessions = Sessions()
        self.db = Database(config.DATABASE)

        # server props
        self.server_address = server_address
        # self.handler = self.handleRequestsUsing(self.clone_factory, self.sessions)

    def __del__(self):
        self.clone_factory.delete()
        self.network.delete()

    def run(self):
        log.info('Starting server on %s ...' % str(self.server_address))
        endpoint_clones = TCP4ServerEndpoint(reactor, 9000)
        endpoint_api = TCP4ServerEndpoint(reactor, 9001)
        endpoint_clones.listen(ProxyFactory(self.clone_factory, self.sessions, self.db))
        endpoint_api.listen(ApiServer(self.clone_factory, self.sessions))

        reactor.run()
        log.info("shutting down...")
        del self
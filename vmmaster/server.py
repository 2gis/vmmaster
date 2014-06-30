from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from .core.clone_factory import CloneFactory
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log
from .core.clone_server import ProxyFactory


class VMMasterServer(object):
    def __init__(self, server_address):
        self.network = Network()
        self.sessions = Sessions()
        self.clone_factory = CloneFactory()

        self.server_address = server_address

    def __del__(self):
        self.sessions.delete()
        self.clone_factory.delete()
        self.network.delete()

    def run(self):
        log.info('Starting server on %s ...' % str(self.server_address))
        endpoint_clones = TCP4ServerEndpoint(reactor, 9000)
        endpoint_clones.listen(ProxyFactory(self.clone_factory, self.sessions))

        reactor.run()
        log.info("shutting down...")
        del self
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint

from .core.platform import Platforms
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log
from .core.platform_server import PlatformServer


class VMMasterServer(object):
    def __init__(self, server_address):
        self.network = Network()
        self.platforms = Platforms()
        self.sessions = Sessions()

        self.server_address = server_address

    def __del__(self):
        self.sessions.delete()
        self.network.delete()

    def run(self):
        log.info('Starting server on %s ...' % str(self.server_address))
        endpoint = TCP4ServerEndpoint(reactor, 9000)
        endpoint.listen(PlatformServer(self.platforms, self.sessions))

        reactor.run()
        log.info("shutting down...")
        del self
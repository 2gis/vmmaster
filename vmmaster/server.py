from twisted.internet.defer import Deferred

from .core.platform import Platforms
from .core.sessions import Sessions
from .core.network.network import Network
from .core.logger import log
from .core.platform_server import PlatformServer


def _block_on(d, timeout=None):
    from Queue import Queue, Empty
    from twisted.internet.defer import TimeoutError
    from twisted.python.failure import Failure
    q = Queue()
    if not isinstance(d, Deferred):
        return None
    d.addBoth(q.put)
    try:
        ret = q.get(timeout is not None, timeout)
    except Empty:
        raise TimeoutError
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret


class VMMasterServer(object):
    def __init__(self, reactor, port):
        self.reactor = reactor
        self.network = Network()
        self.platforms = Platforms()
        self.sessions = Sessions()
        self.bind = self.reactor.listenTCP(port, PlatformServer(self.platforms, self.sessions))
        log.info('Server is listening on %s ...' % port)

    def __del__(self):
        log.info("shutting down...")
        d = self.bind.stopListening()
        _block_on(d, 20)
        self.sessions.delete()
        self.platforms.delete()
        self.network.delete()
        log.info("Server gracefully shut down.")

    def run(self):
        self.reactor.run()
        del self
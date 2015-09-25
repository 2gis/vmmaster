import os
import sys
import multiprocessing
import websockify
from core.config import config

from core.utils.network_utils import get_free_port


class ProxyVNCServer(multiprocessing.Process):
    ws = None

    def __init__(self, host, port):
        super(ProxyVNCServer, self).__init__()
        sys.stderr = sys.stdout = open(os.sep.join([
            config.LOG_DIR, str(port) + '_vnc_proxy.log'
        ]), 'w')

        self.proxy_port = get_free_port()
        sys.argv = [
            "--daemon",
            "--wrap-mode=ignore",
            "--record=%s/proxy_vnc_%s.log" % (config.LOG_DIR, port),
            "0.0.0.0:%d" % self.proxy_port,
            "%s:%s" % (host, port)
        ]

        self.ws = multiprocessing.Process(
            target=websockify.websocketproxy.websockify_init
        )

    def start(self):
        self.ws.start()

    def stop(self):
        if self.ws.is_alive():
            self.ws.terminate()

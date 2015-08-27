# coding: utf-8
import time
import socket
import logging

from functools import wraps

from .utils import to_thread
from ..config import config

log = logging.getLogger('GRAPHITE')


@to_thread
def send_metrics(name, value, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    if hasattr(config, 'GRAPHITE'):
        sock = socket.socket()
        try:
            sock.connect(config.GRAPHITE)
        except Exception, e:
            log.warning(e)
            return
        sock.send("vmmaster.%s %d %d\n" % (name, value, timestamp))
        sock.close()
    else:
        pass


def graphite(value):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            _start = time.time()
            try:
                return f(*args, **kwargs)
            finally:
                send_metrics("%s" % str(value), time.time() - _start)
        return wrapper
    return decorator

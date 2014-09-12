import time
from ..dispatcher import dispatcher, Signals


class VirtualMachine(object):
    name = None
    ip = None
    ready = False

    def __init__(self):
        self.creation_time = time.time()

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)

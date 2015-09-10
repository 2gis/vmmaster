# coding: utf-8

from datetime import datetime
from core.dispatcher import dispatcher, Signals


class VirtualMachine(object):
    def __init__(self, name, platform):
        self.name = name
        self.ip = None
        self.mac = None
        self.platform = platform
        self.created = datetime.now()
        self.ready = False
        self.checking = False
        self.done = False

    @property
    def info(self):
        return {
            "name": str(self.name),
            "ip": str(self.ip),
            "platform": str(self.platform)
        }

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)
        self.done = True

    def is_preloaded(self):
        return 'preloaded' in self.name

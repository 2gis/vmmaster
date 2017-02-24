# coding: utf-8

import time
from core.dispatcher import dispatcher, Signals
from core.db import models


class VirtualMachine(models.Endpoint):
    def __init__(self, name, platform):
        super(VirtualMachine, self).__init__(name, platform)
        self.name = name
        self.ip = None
        self.mac = None
        self.platform = platform
        self.created = time.time()
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
        self.delete()

    def is_preloaded(self):
        return 'preloaded' in self.name

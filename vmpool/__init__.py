# coding: utf-8

from datetime import datetime

from core.dispatcher import dispatcher, Signals
from core.db.models import VirtualMachine as VirtualMachineModel


class VirtualMachine(VirtualMachineModel):
    def __init__(self, name, platform):
        super(VirtualMachine, self).__init__(name, platform)

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)
        self.done = True
        self.deleted = datetime.now()
        self.save()

    def is_preloaded(self):
        return self.name and 'preloaded' in str(self.name)

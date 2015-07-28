# coding: utf-8
import time

from vmmaster.core.dispatcher import dispatcher, Signals
from vmmaster.core.db.models import VirtualMachine as VirtualMachineModel


class VirtualMachine(VirtualMachineModel):
    def __init__(self, name, platform):
        super(VirtualMachine, self).__init__(name, platform)

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)
        self.deleted = True
        self.time_deleted = time.time()
        self.save()

    def is_preloaded(self):
        return self.name and 'preloaded' in str(self.name)

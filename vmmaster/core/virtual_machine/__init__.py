# coding: utf-8

from ..dispatcher import dispatcher, Signals
from vmmaster.core.db.models import VirtualMachine as VirtualMachineModel


class VirtualMachine(VirtualMachineModel):
    def __init__(self, name):
        super(VirtualMachine, self).__init__(name)

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)
        self.deleted = True
        self.save()

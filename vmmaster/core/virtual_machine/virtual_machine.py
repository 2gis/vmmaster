from ..dispatcher import dispatcher, Signals


class VirtualMachine(object):
    name = None
    ip = None

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)

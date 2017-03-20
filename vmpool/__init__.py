# coding: utf-8

from datetime import datetime
from core.dispatcher import dispatcher, Signals
from core.config import config


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
    def ports(self):
        return config.PORTS

    @property
    def vnc_port(self):
        return config.VNC_PORT

    @property
    def selenium_port(self):
        return config.SELENIUM_PORT

    @property
    def agent_port(self):
        return config.VMMASTER_AGENT_PORT

    @property
    def info(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "platform": self.platform
        }

    def create(self):
        pass

    def delete(self):
        dispatcher.send(signal=Signals.DELETE_VIRTUAL_MACHINE, sender=self)
        self.done = True

    def is_preloaded(self):
        return 'preloaded' in self.name

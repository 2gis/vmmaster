import os
import time

from .config import config
from .exceptions import PlatformException
from .dispatcher import dispatcher, Signals
from .virtual_machine.clone_factory import CloneFactory
from .logger import log
from .utils.graphite import send_metrics


class Platform(object):
    name = None

    def get(self, session_id):
        pass


class Origin(Platform):
    name = None
    drive = None
    settings = None

    def __init__(self, name, path, clone_factory):
        self.name = name
        self.clone_factory = clone_factory
        self.drive = os.path.join(path, 'drive.qcow2')
        self.settings = open(os.path.join(path, 'settings.xml'), 'r').read()

    def get(self, session_id):
        super(Origin, self).get(session_id)
        return self.clone_factory.create_clone(self, session_id)


class Platforms(object):
    platforms = dict()

    def __init__(self):
        self.clone_factory = CloneFactory()
        self.vm_count = 0
        self._load_platforms()
        dispatcher.connect(self.__remove_vm, signal=Signals.DELETE_VIRTUAL_MACHINE, sender=dispatcher.Any)

    def delete(self):
        self.clone_factory.delete()
        dispatcher.disconnect(self.__remove_vm, signal=Signals.DELETE_VIRTUAL_MACHINE, sender=dispatcher.Any)

    def _discover_origins(self, origins_dir):
        origins = [origin for origin in os.listdir(origins_dir) if os.path.isdir(os.path.join(origins_dir, origin))]
        return [Origin(origin, os.path.join(origins_dir, origin), self.clone_factory) for origin in origins]

    def _load_platforms(self):
        origins = self._discover_origins(config.ORIGINS_DIR)
        self.platforms = {origin.name: origin for origin in origins}
        log.info("load platforms: %s" % str(self.platforms))

    def _check_platform(self, platform):
        if platform not in self.platforms:
            raise PlatformException("no such platform")

    def _check_vm_count(self):
        if self.vm_count == config.MAX_VM_COUNT:
            raise PlatformException("maximum count of virtual machines already running")

    def create(self, platform, session_id):
        self._check_platform(platform)
        self._check_vm_count()

        self.vm_count += 1
        platform = self.platforms.get(platform, session_id)
        try:
            vm = platform.get(session_id)
            return vm
        except:
            self.vm_count -= 1
            raise

    def __remove_vm(self):
        self.vm_count -= 1
import os

from .config import config
from .exceptions import PlatformException
# from .virtual_machine.virtual_machines_pool import VirtualMachinesPool
from .logger import log


class Platform(object):
    name = None

    def get(self, session_id):
        pass


class Origin(Platform):
    name = None
    drive = None
    settings = None

    def __init__(self, name, path):
        self.name = name
        self.drive = os.path.join(path, 'drive.qcow2')
        self.settings = open(os.path.join(path, 'settings.xml'), 'r').read()


class Platforms(object):
    platforms = dict()

    def __new__(cls, *args, **kwargs):
        log.info("creating platforms")
        inst = object.__new__(cls)
        cls._load_platforms()
        return inst

    @staticmethod
    def _discover_origins(origins_dir):
        origins = [origin for origin in os.listdir(origins_dir) if os.path.isdir(os.path.join(origins_dir, origin))]
        return [Origin(origin, os.path.join(origins_dir, origin)) for origin in origins]

    @classmethod
    def _load_platforms(cls):
        origins = cls._discover_origins(config.ORIGINS_DIR)
        cls.platforms = {origin.name: origin for origin in origins}
        log.info("load platforms: %s" % str(cls.platforms))

    @classmethod
    def check_platform(cls, platform):
        if platform not in cls.platforms:
            raise PlatformException("no such platform")

    @classmethod
    def get(cls, platform):
        cls.check_platform(platform)
        return cls.platforms.get(platform, None)
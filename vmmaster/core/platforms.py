import os

from .config import config
from .exceptions import PlatformException
from .logger import log

from .virtual_machine.clone import KVMClone, OpenstackClone


class Platform(object):
    name = None

    def get(self, session_id):
        pass

    @staticmethod
    def make_clone(origin, prefix):
        raise NotImplementedError


class KVMOrigin(Platform):
    name = None
    drive = None
    settings = None

    def __init__(self, name, path):
        self.name = name
        self.drive = os.path.join(path, 'drive.qcow2')
        self.settings = open(os.path.join(path, 'settings.xml'), 'r').read()

    @staticmethod
    def make_clone(origin, prefix):
        return KVMClone(origin, prefix)


class OpenstackOrigin(Platform):
    name = None

    @staticmethod
    def make_clone(origin, prefix):
        return OpenstackClone(origin, prefix)


class PlatformsInterface(object):
    @classmethod
    def get(cls, platform):
        raise NotImplementedError

    @property
    def platforms(self):
        raise NotImplementedError


class KVMPlatforms(PlatformsInterface):
    platforms = dict()

    def __init__(self):
        self.platforms = self._load_platforms()
        log.info("load kvm platforms: {}".format(str(self.platforms)))

    @staticmethod
    def _discover_origins(origins_dir):
        origins = [origin for origin in os.listdir(origins_dir) if os.path.isdir(os.path.join(origins_dir, origin))]
        return [KVMOrigin(origin, os.path.join(origins_dir, origin)) for origin in origins]

    @classmethod
    def _load_platforms(cls):
        return cls._discover_origins(config.ORIGINS_DIR)


class OpenstackPlatforms(PlatformsInterface):
    pass


class Platforms(object):
    platforms = dict()

    def __new__(cls, *args, **kwargs):
        log.info("creating all platforms")
        inst = object.__new__(cls)
        cls._load_platforms()
        return inst

    @classmethod
    def _load_platforms(cls):
        if config.USE_KVM:
            cls.platforms.update({vm.name: vm for vm in KVMPlatforms().platforms})
        if config.USE_OPENSTACK:
            cls.platforms.update({vm.name: vm for vm in OpenstackPlatforms().platforms})

        log.info("load all platforms: {}".format(str(cls.platforms)))

    @classmethod
    def check_platform(cls, platform):
        if platform not in cls.platforms.keys():
            raise PlatformException("no such platform")

    @classmethod
    def get(cls, platform):
        cls.check_platform(platform)
        return cls.platforms.get(platform, None)
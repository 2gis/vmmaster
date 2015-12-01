# coding: utf-8

import os

from core.config import config
from core.logger import log_pool
from core.utils import openstack_utils


class Platform(object):
    name = None

    def get(self, session_id):
        pass

    @staticmethod
    def make_clone(origin, prefix):
        raise NotImplementedError


class KVMOrigin(Platform):
    drive = None
    settings = None

    def __init__(self, name, path):
        self.name = name
        self.drive = os.path.join(path, 'drive.qcow2')
        self.settings = open(os.path.join(path, 'settings.xml'), 'r').read()

    @staticmethod
    def make_clone(origin, prefix):
        from clone import KVMClone
        return KVMClone(origin, prefix)


class OpenstackOrigin(Platform):
    def __init__(self, origin):
        self.client = openstack_utils.nova_client()
        self.id = origin.id
        self.name = origin.name
        self.short_name = origin.name.split(
            config.OPENSTACK_PLATFORM_NAME_PREFIX)[1]
        self.min_disk = origin.min_disk
        self.min_ram = origin.min_ram

        try:
            self.flavor_id = origin.instance_type_flavorid
            self.flavor_name = (
                lambda s: s.client.flavors.get(s.flavor_id).name)(self)
        except Exception:
            self.flavor_name = config.OPENSTACK_DEFAULT_FLAVOR

    @staticmethod
    def make_clone(origin, prefix):
        from clone import OpenstackClone
        return OpenstackClone(origin, prefix)


class PlatformsInterface(object):
    @classmethod
    def get(cls, platform):
        raise NotImplementedError

    @property
    def platforms(self):
        raise NotImplementedError

    @staticmethod
    def max_count():
        raise NotImplementedError

    @staticmethod
    def can_produce(platform):
        raise NotImplementedError


class KVMPlatforms(PlatformsInterface):
    @staticmethod
    def _discover_origins(origins_dir):
        origins = [origin for origin in os.listdir(origins_dir)
                   if os.path.isdir(os.path.join(origins_dir, origin))]
        return [KVMOrigin(origin, os.path.join(origins_dir, origin))
                for origin in origins]

    @property
    def platforms(self):
        return self._discover_origins(config.ORIGINS_DIR)

    @staticmethod
    def max_count():
        return config.KVM_MAX_VM_COUNT

    @staticmethod
    def can_produce(platform):
        return KVMPlatforms.max_count()


class OpenstackPlatforms(PlatformsInterface):
    @classmethod
    def limits(cls, if_none):
        return openstack_utils.nova_client().limits.get().to_dict().get(
            'absolute', if_none)

    @classmethod
    def flavor_params(cls, flavor_name):
        return openstack_utils.nova_client().flavors.find(
            name=flavor_name).to_dict()

    @staticmethod
    def images():
        return openstack_utils.glance_client().images.list()

    @property
    def platforms(self):
        origins = \
            [image for image in self.images()
             if image.status == 'active'
             and config.OPENSTACK_PLATFORM_NAME_PREFIX in image.name]

        _platforms = [OpenstackOrigin(origin) for origin in origins]
        return _platforms

    @staticmethod
    def max_count():
        config_max_count = config.OPENSTACK_MAX_VM_COUNT
        limits = OpenstackPlatforms.limits(if_none={'maxTotalInstances': 0})

        if config_max_count <= limits.get('maxTotalInstances', 0):
            max_count = config_max_count
            # Maximum count of virtual machines use from vmmaster config
        else:
            max_count = limits.get('maxTotalInstances', 0)
            # Maximum count of virtual machines use from openstack limits

        return max_count

    @staticmethod
    def can_produce(platform):
        limits = OpenstackPlatforms.limits(if_none={
            'maxTotalCores': 0, 'maxTotalInstances': 0, 'maxTotalRAMSize': 0,
            'totalCoresUsed': 0, 'totalInstancesUsed': 0, 'totalRAMUsed': 0})

        flavor_params = OpenstackPlatforms.flavor_params(
            Platforms.get(platform).flavor_name)
        if limits.get('totalInstancesUsed', 0) >= \
                limits.get('maxTotalInstances', 0):
            log_pool.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough Instances resources' % platform
            )
            return 0

        if flavor_params.get('vcpus', 0) >= \
                limits.get('maxTotalCores', 0) - \
                limits.get('totalCoresUsed', 0):
            log_pool.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough CPU resources' % platform
            )
            return 0

        if flavor_params.get('ram', 0) >= \
                limits.get('maxTotalRAMSize', 0) - \
                limits.get('totalRAMUsed', 0):
            log_pool.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough RAM resources' % platform
            )
            return 0

        return OpenstackPlatforms.max_count()


class Platforms(object):
    platforms = dict()
    kvm_platforms = None
    openstack_platforms = None

    def __new__(cls, *args, **kwargs):
        log_pool.info("Load platforms...")
        inst = object.__new__(cls)
        if config.USE_KVM:
            cls.kvm_platforms = {vm.name: vm for vm in
                                 KVMPlatforms().platforms}
            log_pool.info("KVM platforms: {}".format(
                cls.kvm_platforms.keys())
            )
        if config.USE_OPENSTACK:
            cls.openstack_platforms = {vm.short_name: vm for vm in
                                       OpenstackPlatforms().platforms}
            log_pool.info("Openstack platforms: {}".format(
                cls.openstack_platforms.keys())
            )
        cls._load_platforms()
        return inst

    @classmethod
    def _load_platforms(cls):
        if bool(cls.kvm_platforms):
            cls.platforms.update(cls.kvm_platforms)
        if bool(cls.openstack_platforms):
            cls.platforms.update(cls.openstack_platforms)

        log_pool.info("Platforms loaded: {}".format(str(cls.platforms.keys())))

    @classmethod
    def max_count(cls):
        m_count = 0
        if bool(cls.kvm_platforms):
            m_count += KVMPlatforms.max_count()
        if bool(cls.openstack_platforms):
            m_count += OpenstackPlatforms.max_count()
        return m_count

    @classmethod
    def can_produce(cls, platform):
        if config.USE_KVM and platform in cls.kvm_platforms.keys():
            return KVMPlatforms.can_produce(platform)
        if config.USE_OPENSTACK and platform in cls.openstack_platforms.keys():
            return OpenstackPlatforms.can_produce(platform)

    @classmethod
    def check_platform(cls, platform):
        if platform in cls.platforms.keys():
            return True
        else:
            return False

    @classmethod
    def get(cls, platform):
        cls.check_platform(platform)
        return cls.platforms.get(platform, None)

    @classmethod
    def info(cls):
        if hasattr(config, 'PLATFORM') and config.PLATFORM:
            return config.PLATFORM
        return list(cls.platforms.keys())

    @classmethod
    def cleanup(cls):
        if bool(cls.kvm_platforms):
            for platform in cls.kvm_platforms:
                del cls.platforms[platform]
            cls.kvm_platforms = None
        if bool(cls.openstack_platforms):
            for platform in cls.openstack_platforms:
                del cls.platforms[platform]
            cls.openstack_platforms = None

# coding: utf-8

import logging

from core.config import config
from core.utils import openstack_utils, exception_handler
from core.clients.docker_client import DockerManageClient

UnlimitedCount = type("UnlimitedCount", (), {})()
log = logging.getLogger(__name__)


class Platform(object):
    name = None

    def get(self, session_id):
        pass

    @staticmethod
    def make_clone(origin, prefix, pool):
        raise NotImplementedError


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
    def make_clone(origin, prefix, pool):
        from core.db.models import OpenstackClone
        return OpenstackClone(origin, prefix, pool)


class DockerImage(Platform):
    def __init__(self, origin):
        self.origin = origin
        self.name = self.get_name()
        self.short_name = self.name.replace(config.DOCKER_IMAGE_NAME_PREFIX, "")

    @exception_handler()
    def short_id(self):
        return self.origin.short_id

    @exception_handler()
    def get_name(self):
        tags = self.tags()
        if isinstance(tags, list) and len(tags):
            return tags[0].strip()

    @exception_handler()
    def tags(self):
        return self.origin.tags

    @staticmethod
    def make_clone(origin, prefix, pool):
        from core.db.models import DockerClone
        return DockerClone(origin, prefix, pool)


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
    def get_limit(platform):
        raise NotImplementedError


class DockerPlatforms(PlatformsInterface):
    client = DockerManageClient()

    def __init__(self, database):
        self.database = database

        from core.db.models import DockerClone
        self.clone_class = DockerClone

    @classmethod
    def get(cls, platform):
        return cls.client.get_image(name=platform)

    def prepare_platforms(self):
        for platform_type in config.PLATFORMS.values():
            for platform_name in platform_type:
                try:
                    image_name, image_tag = platform_name.split(":")
                except ValueError:
                    log.warning("Wrong platform name {} (must be: image_name:tag)".format(platform_name))
                    continue
                log.info("Pull image: {}{}".format(
                    config.DOCKER_IMAGE_NAME_PREFIX,
                    platform_name))
                self.client.pull_image(
                    name="{}{}".format(config.DOCKER_IMAGE_NAME_PREFIX, image_name),
                    tag=image_tag
                )

    @property
    def platforms(self):
        return [image for image in self.client.images() if config.DOCKER_IMAGE_NAME_PREFIX in image.name]

    @staticmethod
    def max_count():
        return config.DOCKER_MAX_COUNT

    @staticmethod
    def get_limit(platform):
        # FIXME: make classmethod
        return DockerPlatforms.max_count()


class OpenstackPlatforms(PlatformsInterface):
    def __init__(self, database):
        self.database = database

        from core.db.models import OpenstackClone
        self.clone_class = OpenstackClone

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
        return openstack_utils.nova_client().glance.list()

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
        return config.OPENSTACK_MAX_VM_COUNT

    @staticmethod
    def get_limit(platform):
        return OpenstackPlatforms.max_count()


class Platforms(object):
    provider_id = None
    platforms = {}
    openstack_platforms = {}
    docker_platforms = {}

    def __init__(self, database):
        log.info("Loading platforms...")

        self.db = database
        self.openstack = OpenstackPlatforms(database)
        self.docker = DockerPlatforms(database)

        if config.USE_OPENSTACK:
            self.openstack_platforms = {vm.short_name: vm for vm in self.openstack.platforms}
            log.info("Openstack platforms: {}".format(
                self.openstack_platforms.keys())
            )
        if config.USE_DOCKER:
            self.docker.prepare_platforms()
            self.docker_platforms = {vm.short_name: vm for vm in self.docker.platforms}
            log.info("Docker platforms: {}".format(
                self.docker_platforms.keys())
            )
        self._load_platforms()

    def _load_platforms(self):
        if bool(self.openstack_platforms):
            self.platforms.update(self.openstack_platforms)
        if bool(self.docker_platforms):
            self.platforms.update(self.docker_platforms)

        log.info("Platforms loaded: {}".format(str(self.platforms.keys())))

    def max_count(self):
        m_count = 0
        if bool(self.openstack_platforms):
            m_count += self.openstack.max_count()
        if bool(self.docker_platforms):
            m_count += self.docker.max_count()
        return m_count

    def get_limit(self, platform):
        if config.USE_OPENSTACK and platform in self.openstack_platforms.keys():
            return self.openstack.get_limit(platform)
        if config.USE_DOCKER and platform in self.docker_platforms.keys():
            return self.docker.get_limit(platform)

    def check_platform(self, platform):
        if platform in self.platforms.keys():
            return True
        else:
            return False

    def get(self, platform):
        self.check_platform(platform)
        return self.platforms.get(platform, None)

    def get_endpoint(self, endpoint_id):
        return self.db.get_endpoint(endpoint_id)

    def get_endpoints(self, efilter="all"):
        return self.db.get_endpoints(provider_id=self.provider_id, efilter=efilter)

    def get_all_endpoints(self):
        return self.get_endpoints(efilter="all")

    @property
    def pool(self):
        return self.get_endpoints(efilter="pool")

    @property
    def using(self):
        return self.get_endpoints(efilter="using")

    @property
    def wait_for_service(self):
        return self.get_endpoints(efilter="wait for service")

    @property
    def on_service(self):
        return self.get_endpoints(efilter="service")

    @property
    def active_endpoints(self):
        return self.get_endpoints(efilter="active")

    def info(self):
        return list(self.platforms.keys())

    def cleanup(self):
        if bool(self.openstack_platforms):
            for platform in self.openstack_platforms:
                del self.platforms[platform]
            self.openstack_platforms = {}
        if bool(self.docker_platforms):
            for platform in self.docker_platforms:
                del self.platforms[platform]
            self.docker_platforms = {}

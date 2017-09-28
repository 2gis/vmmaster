# coding: utf-8

import time
import logging
from threading import Thread, Lock
from collections import defaultdict

from core.config import config
from core.network import DockerNetwork
from vmpool.platforms import Platforms, UnlimitedCount
from vmpool.artifact_collector import ArtifactCollector
from vmpool.matcher import SeleniumMatcher, PoolBasedMatcher

log = logging.getLogger(__name__)


class VirtualMachinesPoolPreloader(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.app = pool.app
        self.running = True
        self.daemon = True
        self.pool = pool

    def run(self):
        log.info("Preloader started...")
        with self.app.app_context():
            while self.running:
                try:
                    platform_name = self.need_load()
                    if platform_name is not None:
                        self.pool.preload(platform_name, "preloaded")
                except Exception as e:
                    log.exception('Exception in preloader: %s', e.message)

                time.sleep(config.PRELOADER_FREQUENCY)

    def need_load(self):
        preloaded = [vm for vm in self.pool.active_endpoints if vm.is_preloaded()]
        already_have = self.pool.count_virtual_machines(preloaded)
        platforms = {}

        if config.USE_OPENSTACK:
            platforms.update(config.OPENSTACK_PRELOADED)
        if config.USE_DOCKER:
            platforms.update(config.DOCKER_PRELOADED)

        for platform_name, need in platforms.iteritems():
            have = already_have.get(platform_name, 0)
            if need > have:
                return platform_name

    def stop(self):
        self.running = False
        self.join(1)
        log.info("Preloader stopped")


class VirtualMachinesPool(object):
    if config.USE_DOCKER and not config.BIND_LOCALHOST_PORTS:
        network = DockerNetwork()
    id = None
    lock = Lock()
    platforms = None
    preloader = None
    artifact_collector = None

    def __str__(self):
        return str(self.active_endpoints)

    def __init__(self, app, platforms_class=Platforms, matcher_class=SeleniumMatcher,
                 preloader_class=VirtualMachinesPoolPreloader, artifact_collector_class=ArtifactCollector):
        self.app = app
        self.platforms = platforms_class()
        self.preloader = preloader_class(self)
        self.matcher = matcher_class(platforms=config.PLATFORMS, fallback_matcher=PoolBasedMatcher(self.platforms))
        self.artifact_collector = artifact_collector_class()

    def register(self):
        return self.app.database.register_provider(
            name="Unnamed provider",
            url="%s:%s" % ("localhost", config.PORT),
            platforms=self.platforms.info()
        )

    def unregister(self):
        self.app.database.unregister_provider(self.id)

    @property
    def active_endpoints(self):
        return self.platforms.get_endpoints(self.id, efilter="active")

    def get_all_endpoints(self):
        return self.platforms.get_endpoints(self.id, efilter="all")

    @property
    def pool(self):
        return self.platforms.get_endpoints(self.id, efilter="pool")

    @property
    def using(self):
        return self.platforms.get_endpoints(self.id, efilter="using")

    def start_workers(self):
        self.id = self.register()
        self.preloader.start()

    def stop_workers(self):
        if self.preloader:
            self.preloader.stop()
        if self.artifact_collector:
            self.artifact_collector.stop()
        self.free()
        self.unregister()
        self.platforms.cleanup()

    def free(self):
        log.info("Deleting machines...")
        with self.app.app_context():
            for vm in self.active_endpoints:
                vm.delete(try_to_rebuild=False)

    def count(self):
        return len(self.active_endpoints)

    def can_produce(self, platform_name):
        platform_limit = self.platforms.get_limit(platform_name)

        if platform_limit is UnlimitedCount:
            return True

        current_count = self.count()
        if current_count >= platform_limit:
            log.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough Instances resources. Current(%s), Limit(%s)'
                % (platform_name, current_count, platform_limit)
            )
            return False
        else:
            return True

    def has(self, platform_name):
        for vm in self.pool:
            if vm.platform_name == platform_name and vm.ready:
                return True
        return False

    def get_by_platform(self, platform_name):
        res = None

        with self.lock:
            if not self.has(platform_name):
                return None

            for vm in sorted(self.pool, key=lambda v: v.created_time, reverse=True):
                if vm.platform_name == platform_name and vm.ready:
                    log.info(
                        "Got VM %s (ip=%s, ready=%s)" %
                        (vm.name, vm.ip, vm.ready)
                    )
                    res = vm
                    vm.set_in_use(True)
                    break

        if not res:
            return None

        if res.ping_vm(vm.bind_ports):
            return res
        else:
            res.delete()
            return None

    def get_by_name(self, _name=None):
        # TODO: remove get_by_name
        if _name:
            log.debug('Getting VM: %s' % _name)
            for vm in self.active_endpoints:
                if vm.name == _name:
                    return vm

    def get_by_id(self, endpoint_id):
        return self.platforms.get_endpoint(endpoint_id)

    @staticmethod
    def count_virtual_machines(it):
        result = defaultdict(int)
        for vm in it:
            result[vm.platform_name] += 1

        return result

    def pooled_virtual_machines(self):
        return self.count_virtual_machines(self.pool)

    def using_virtual_machines(self):
        return self.count_virtual_machines(self.using)

    def add(self, platform_name, prefix="ondemand"):
        if prefix == "preloaded":
            log.info("Preloading %s." % platform_name)

        with self.lock:
            if not self.can_produce(platform_name):
                return None

            origin = self.platforms.get(platform_name)
            try:
                clone = origin.make_clone(origin, prefix, self)
                if not clone.is_preloaded():
                    clone.set_in_use(True)
            except Exception as e:
                log.exception(
                    'Exception during initializing vm object: %s' % e.message
                )
                return None

        try:
            clone.create()
        except Exception as e:
            log.exception("Error creating vm: %s" % e.message)
            clone.delete()

        return clone

    def get_vm(self, platform_name):
        vm = self.get_by_platform(platform_name)

        if vm:
            return vm

        vm = self.add(platform_name)

        if vm:
            return vm

    def preload(self, origin_name, prefix="preloaded"):
        return self.add(origin_name, prefix)

    @property
    def info(self):
        def print_view(lst):
            return [{
                "name": l.name,
                "ip": l.ip,
                "ready": l.ready,
                "created": l.created_time,
                "ports": l.ports
            } for l in lst]

        return {
            "pool": {
                'count': self.pooled_virtual_machines(),
                'list': print_view(self.pool),
            },
            "using": {
                'count': self.using_virtual_machines(),
                'list': print_view(self.using),
            },
            "already_use": self.count(),
        }

    def get_matched_platforms(self, dc):
        return self.matcher.get_matched_platforms(dc)

    def check_platform(self, platform):
        return self.platforms.check_platform(platform)

    def start_recorder(self, session):
        return self.artifact_collector.record_screencast(session.id, self.app)

    def save_artifacts(self, session):
        return self.artifact_collector.save_selenium_log(session.id, self.app)

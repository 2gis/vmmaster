# coding: utf-8

import time
import logging
from threading import Thread, Lock
from collections import defaultdict

from core.config import config
from vmpool.endpoint import EndpointWorker
from vmpool.platforms import Platforms, UnlimitedCount

log = logging.getLogger(__name__)


class VirtualMachinesPool(object):
    lock = Lock()
    platforms = None
    preloader = None
    endpoint_worker = None

    def __str__(self):
        return str(self.get_endpoints())

    def __init__(self, app):
        self.app = app
        self.platforms = Platforms()

    def get_endpoints(self):
        return self.app.database.get_endpoints(self.app.id, efilter="active")

    def get_all_endpoints(self):
        return self.app.database.get_endpoints(self.app.id, efilter="all")

    def get_endpoints_in_ready(self):
        return self.app.database.get_endpoints(self.app.id, efilter="pool")

    def get_endpoints_in_use(self):
        return self.app.database.get_endpoints(self.app.id, efilter="using")

    def start_workers(self):
        self.preloader = VirtualMachinesPoolPreloader(self)
        self.preloader.start()
        # self.endpoint_worker = EndpointWorker(self)
        # self.endpoint_worker.start()

    def stop_workers(self):
        if self.endpoint_worker:
            self.endpoint_worker.stop()
        if self.preloader:
            self.preloader.stop()

    def free(self):
        log.info("Deleting machines...")
        with self.app.app_context():
            for vm in self.get_endpoints():
                vm.delete(try_to_rebuild=False)

    def count(self):
        return len(self.get_endpoints())

    def can_produce(self, platform):
        platform_limit = self.platforms.get_limit(platform)

        if platform_limit is UnlimitedCount:
            return True

        current_count = self.count()
        if current_count >= platform_limit:
            log.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough Instances resources. Current(%s), Limit(%s)'
                % (platform, current_count, platform_limit)
            )
            return False
        else:
            return True

    def has(self, platform):
        for vm in self.get_endpoints_in_ready():
            if vm.platform == platform and vm.ready:
                return True
        return False

    def get_by_platform(self, platform):
        res = None

        with self.lock:
            if not self.has(platform):
                return None

            for vm in sorted(self.get_endpoints_in_ready(), key=lambda v: v.created_time, reverse=True):
                if vm.platform == platform and vm.ready:
                    log.info(
                        "Got VM %s (ip=%s, ready=%s)" %
                        (vm.name, vm.ip, vm.ready)
                    )
                    res = vm
                    break

        if not res:
            return None

        if res.ping_vm():
            return res
        else:
            res.delete()
            return None

    def get_by_name(self, _name=None):
        # TODO: remove get_by_name
        if _name:
            log.debug('Getting VM: %s' % _name)
            for vm in self.get_endpoints():
                if vm.name == _name:
                    return vm

    @staticmethod
    def count_virtual_machines(it):
        result = defaultdict(int)
        for vm in it:
            result[vm.platform] += 1

        return result

    def pooled_virtual_machines(self):
        return self.count_virtual_machines(self.get_endpoints_in_ready())

    def using_virtual_machines(self):
        return self.count_virtual_machines(self.get_endpoints_in_use())

    def add(self, platform, prefix="ondemand"):
        if prefix == "preloaded":
            log.info("Preloading %s." % platform)

        with self.lock:
            if not self.can_produce(platform):
                return None

            origin = self.platforms.get(platform)
            try:
                clone = origin.make_clone(origin, prefix, self)
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

    def get_vm(self, platform):
        vm = self.get_by_platform(platform)

        if vm:
            return vm

        vm = self.add(platform)

        if vm:
            return vm

    def save_artifact(self, session_id, artifacts):
        return self.artifact_collector.add_tasks(session_id, artifacts)

    def preload(self, origin_name, prefix=None):
        return self.add(origin_name, prefix)

    def return_vm(self, vm):
        pass

    @property
    def info(self):
        def print_view(lst):
            return [{"name": l.name, "ip": l.ip,
                     "ready": l.ready,
                     "created": l.created_time} for l in lst]

        return {
            "pool": {
                'count': self.pooled_virtual_machines(),
                'list': print_view(self.get_endpoints_in_ready()),
            },
            "using": {
                'count': self.using_virtual_machines(),
                'list': print_view(self.get_endpoints_in_use()),
            },
            "already_use": self.count(),
        }


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
                    platform = self.need_load()
                    if platform is not None:
                        self.pool.preload(platform, "preloaded")
                except Exception as e:
                    log.exception('Exception in preloader: %s', e.message)

                time.sleep(config.PRELOADER_FREQUENCY)

    def need_load(self):
        preloaded = [vm for vm in self.pool.get_endpoints() if vm.is_preloaded()]
        already_have = self.pool.count_virtual_machines(preloaded)
        platforms = {}

        if config.USE_OPENSTACK:
            platforms.update(config.OPENSTACK_PRELOADED)

        for platform, need in platforms.iteritems():
            have = already_have.get(platform, 0)
            if need > have:
                return platform

    def stop(self):
        self.running = False
        self.join(1)
        log.info("Preloader stopped")

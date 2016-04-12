# coding: utf-8

import time
from threading import Thread, Lock
from collections import defaultdict

from core.config import config
from core.logger import log_pool
from core.network import Network

from vmpool.platforms import Platforms, UnlimitedCount


class VirtualMachinesPool(object):
    pool = list()
    using = list()
    network = Network()
    lock = Lock()
    platforms = Platforms

    def __str__(self):
        return str(self.pool)

    def __init__(self):
        self.platforms()
        self.preloader = VirtualMachinesPoolPreloader(self)
        self.preloader.start()

    @classmethod
    def remove_vm(cls, vm):
        if vm in list(cls.using):
            try:
                cls.using.remove(vm)
            except ValueError:
                log_pool.warning("VM %s not found in using" % vm.name)
        if vm in list(cls.pool):
            try:
                cls.pool.remove(vm)
            except ValueError:
                log_pool.warning("VM %s not found in pool" % vm.name)

    @classmethod
    def add_vm(cls, vm, to=None):
        if to is None:
            to = cls.pool
        to.append(vm)

    @classmethod
    def free(cls):
        log_pool.info("Deleting using machines...")
        for vm in list(cls.using):
            cls.using.remove(vm)
            vm.delete(try_to_rebuild=False)
        log_pool.info("Deleting pool...")
        for vm in list(cls.pool):
            cls.pool.remove(vm)
            vm.delete(try_to_rebuild=False)
        cls.network.delete()

    @classmethod
    def count(cls):
        return len(cls.pool) + len(cls.using)

    @classmethod
    def can_produce(cls, platform):
        platform_limit = cls.platforms.get_limit(platform)

        if platform_limit is UnlimitedCount:
            return True

        if cls.count() >= platform_limit:
            log_pool.warning(
                'Can\'t produce new virtual machine with platform %s: '
                'not enough Instances resources' % platform
            )
            return False
        else:
            return True

    @classmethod
    def has(cls, platform):
        for vm in cls.pool:
            if vm.platform == platform and vm.ready and not vm.checking:
                return True
        return False

    @classmethod
    def get_by_platform(cls, platform):
        res = None

        with cls.lock:
            if not cls.has(platform):
                return None

            for vm in sorted(cls.pool, key=lambda v: v.created, reverse=True):
                if vm.platform == platform and vm.ready and not vm.checking:
                    log_pool.info(
                        "Got VM %s (ip=%s, ready=%s, checking=%s)" %
                        (vm.name, vm.ip, vm.ready, vm.checking)
                    )
                    cls.pool.remove(vm)
                    cls.using.append(vm)
                    res = vm
                    break

        if not res:
            return None

        if res.ping_vm():
            return res
        else:
            cls.using.remove(res)
            res.delete()
            return None

    @classmethod
    def get_by_name(cls, _name=None):
        # TODO: remove get_by_name
        if _name:
            log_pool.debug('Getting VM: %s' % _name)
            for vm in cls.pool + cls.using:
                if vm.name == _name:
                    return vm

    @classmethod
    def count_virtual_machines(cls, it):
        result = defaultdict(int)
        for vm in it:
            result[vm.platform] += 1

        return result

    @classmethod
    def pooled_virtual_machines(cls):
        return cls.count_virtual_machines(cls.pool)

    @classmethod
    def using_virtual_machines(cls):
        return cls.count_virtual_machines(cls.using)

    @classmethod
    def add(cls, platform, prefix="ondemand", to=None):
        if prefix == "preloaded":
            log_pool.info("Preloading %s." % platform)

        if to is None:
            to = cls.using

        with cls.lock:
            if not cls.can_produce(platform):
                return None

            origin = cls.platforms.get(platform)
            try:
                clone = origin.make_clone(origin, prefix, cls)
            except Exception as e:
                log_pool.info(
                    'Exception during initializing vm object: %s' % e.message
                )
                return None

            cls.add_vm(clone, to)

        try:
            clone.create()
        except Exception as e:
            log_pool.error("Error creating vm: %s" % e.message)
            clone.delete()
            try:
                to.remove(clone)
            except ValueError:
                log_pool.warning("VM %s not found while removing" % clone.name)
            return None

        return clone

    @classmethod
    def get_vm(cls, platform):
        vm = cls.get_by_platform(platform)

        if vm:
            return vm

        vm = cls.add(platform)

        if vm:
            return vm

    @classmethod
    def preload(cls, origin_name, prefix=None):
        return cls.add(origin_name, prefix, to=cls.pool)

    @classmethod
    def return_vm(cls, vm):
        cls.using.remove(vm)
        cls.pool.append(vm)

    @property
    def info(self):
        def print_view(lst):
            return [{"name": l.name, "ip": l.ip,
                     "ready": l.ready, "checking": l.checking,
                     "created": l.created} for l in lst]

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


class VirtualMachinesPoolPreloader(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.pool = pool

    def run(self):
        while self.running:
            try:
                platform = self.need_load()
                if platform is not None:
                    self.pool.preload(platform, "preloaded")
            except Exception as e:
                log_pool.exception('Exception in preloader: %s', e.message)

            time.sleep(config.PRELOADER_FREQUENCY)

    def need_load(self):
        if self.pool.using is not []:
            using = [vm for vm in self.pool.using
                     if vm.is_preloaded()]
        else:
            using = []
        already_have = self.pool.count_virtual_machines(self.pool.pool + using)
        platforms = {}

        if config.USE_KVM:
            platforms.update(config.KVM_PRELOADED)
        if config.USE_OPENSTACK:
            platforms.update(config.OPENSTACK_PRELOADED)

        for platform, need in platforms.iteritems():
            have = already_have.get(platform, 0)
            if need > have:
                return platform

    def stop(self):
        self.running = False
        self.join(1)
        log_pool.info("Preloader stopped")

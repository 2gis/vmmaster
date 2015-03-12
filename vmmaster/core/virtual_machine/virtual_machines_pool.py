# coding: utf-8
import time
from threading import Thread
from collections import defaultdict
from uuid import uuid4

from .clone import Clone

from ..exceptions import CreationException
from ..config import config
from ..logger import log


class VirtualMachinesPool(object):
    pool = list()
    using = list()

    def __str__(self):
        return str(self.pool)

    @classmethod
    def remove_vm(cls, vm):
        cls.using.remove(vm)

    @classmethod
    def add_vm(cls, vm, to):
        to.append(vm)

    @classmethod
    def free(cls):
        log.info("deleting using machines")
        for vm in list(cls.using):
            cls.using.remove(vm)
            vm.delete()
        log.info("deleting pool")
        for vm in list(cls.pool):
            cls.pool.remove(vm)
            vm.delete()

    @classmethod
    def count(cls):
        return len(cls.pool) + len(cls.using)

    @classmethod
    def can_produce(cls):
        max_count = 0

        if config.USE_KVM:
            max_count += config.KVM_MAX_VM_COUNT
        if config.USE_OPENSTACK:
            max_count += config.OPENSTACK_MAX_VM_COUNT

        return max_count - cls.count()

    @classmethod
    def has(cls, platform):
        for vm in cls.pool:
            if vm.platform == platform and vm.ready:
                return True

        return False

    @classmethod
    def get(cls, platform):
        for vm in sorted(cls.pool, key=lambda v: v.creation_time):
            if vm.platform == platform and vm.ready:
                cls.pool.remove(vm)
                cls.using.append(vm)
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
    def add(cls, origin_name, prefix=None, to=None):
        from ..platforms import Platforms

        if not cls.can_produce():
            raise CreationException("maximum count of virtual machines already running")

        if to is None:
            to = cls.using

        if prefix is None:
            prefix = "ondemand-{}".format(uuid4())

        origin = Platforms.get(origin_name)
        clone = origin.make_clone(origin, prefix)

        cls.add_vm(clone, to)

        try:
            clone.create()
        except Exception as e:
            log.error(e)
            clone.delete()
            to.remove(clone)
            return

        return clone

    @classmethod
    def preload(cls, origin_name, prefix=None):
        return cls.add(origin_name, prefix, to=cls.pool)

    @classmethod
    def return_vm(cls, vm):
        cls.using.remove(vm)
        cls.pool.append(vm)

    @property
    def info(self):
        return {
            "pool": self.pooled_virtual_machines(),
            "can_produce": self.can_produce()
        }


class VirtualMachinesPoolPreloader(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.pool = pool

    def run(self):
        while self.running:
            if self.pool.can_produce():
                platform = self.need_load()
                if platform is not None:
                    self.pool.preload(platform, "preloaded-{}".format(uuid4()))

            time.sleep(1)

    def need_load(self):
        already_have = self.pool.pooled_virtual_machines()
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
        log.info("Preloader stopping...")
        self.running = False
        self.join()
        log.info("Preloader stopped")


class VirtualMachineChecker(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.pool = pool

    def run(self):
        while self.running:
            self.fix_broken_vm()
            time.sleep(config.VM_CHECK_TIMEOUT)

    def fix_broken_vm(self):
        for vm in self.pool.pool:
            if vm.ready:
                log.info("Check for {clone} with ip: {ip}:{port}".format(clone=vm.name, ip=vm.ip, port=config.SELENIUM_PORT))
                if not vm.vm_is_ready:
                    try:
                        vm.rebuild()
                    except Exception as e:
                        log.error(e)
                        vm.delete()
                        self.pool.remove(vm)

    def stop(self):
        log.info("VMChecker stopping...")
        self.running = False
        self.join()
        log.info("VMChecker stopped")


pool = VirtualMachinesPool()
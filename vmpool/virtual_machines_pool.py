# coding: utf-8

import time
from threading import Thread
from collections import defaultdict

from core.exceptions import CreationException
from core.config import config
from core.logger import log
from core.network import Network

from platforms import Platforms
from flask import current_app


class VirtualMachinesPool(object):
    pool = list()
    using = list()
    network = Network()

    def __str__(self):
        return str(self.pool)

    @classmethod
    def remove_vm(cls, vm):
        if vm in list(cls.using):
            try:
                cls.using.remove(vm)
            except ValueError:
                pass
        if vm in list(cls.pool):
            try:
                cls.pool.remove(vm)
            except ValueError:
                pass

    @classmethod
    def add_vm(cls, vm, to=None):
        if to is None:
            to = cls.pool
        to.append(vm)

    @classmethod
    def free(cls):
        log.info("Deleting using machines")
        for vm in list(cls.using):
            cls.using.remove(vm)
            vm.delete(try_to_rebuild=False)
        log.info("Deleting pool")
        for vm in list(cls.pool):
            cls.pool.remove(vm)
            vm.delete(try_to_rebuild=False)
        cls.network.delete()

    @classmethod
    def count(cls):
        return len(cls.pool) + len(cls.using)

    @classmethod
    def can_produce(cls, platform):
        if cls.count() >= Platforms.can_produce(platform):
            log.debug(
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
    def get_by_platform(cls, platform=None):
        if platform:
            for vm in sorted(cls.pool, key=lambda v: v.created,
                             reverse=True):
                if vm.platform == platform and vm.ready and not vm.checking:
                    log.info(
                        "Got VM %s (ip=%s, ready=%s, checking=%s)" %
                        (vm.name, vm.ip, vm.ready, vm.checking)
                    )
                    if vm.ping_vm():
                        cls.pool.remove(vm)
                        cls.using.append(vm)
                        return vm
                    else:
                        cls.pool.remove(vm)
                        vm.delete()

    @classmethod
    def get_by_name(cls, _name=None):
        if _name:
            log.debug('Getting VM: %s' % _name)
            for vm in cls.pool + cls.using:
                if vm.ready and vm.name == _name:
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
    def add(cls, platform, prefix=None, to=None):
        if not cls.can_produce(platform):
            raise CreationException(
                "Maximum count of virtual machines already running")

        if to is None:
            to = cls.using

        if prefix is None:
            prefix = "ondemand"

        origin = Platforms.get(platform)
        try:
            clone = origin.make_clone(origin, prefix)
        except Exception as e:
            log.info('Exception during initializing vm object: %s' % e.message)
            return

        cls.add_vm(clone, to)

        try:
            clone.create()
        except Exception as e:
            log.error("Error creating vm: %s" % e.message)
            clone.delete()
            try:
                to.remove(clone)
            except ValueError:
                pass
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
            "max_count": current_app.platforms.max_count(),
            "already_use": self.count(),
            "can_produce": current_app.platforms.max_count() - self.count()
        }


class VirtualMachinesPoolPreloader(Thread):
    def __init__(self, _pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.pool = _pool

    def run(self):
        while self.running:
            platform = self.need_load()
            if platform is not None:
                if self.pool.can_produce(platform):
                    log.info("Preloading vm for platform %s." % platform)
                    self.pool.preload(platform, "preloaded")

            time.sleep(config.PRELOADER_FREQUENCY)

    def need_load(self):
        if self.pool.using is not []:
            using = [vm for vm in self.pool.using
                     if 'preloaded' in str(vm.prefix)]
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
        log.info("Preloader stopped")


class VirtualMachineChecker(Thread):
    def __init__(self, _pool):
        Thread.__init__(self)
        self.running = config.VM_CHECK
        self.daemon = True
        self.pool = _pool

    def run(self):
        while self.running:
            self.fix_broken_vm()
            time.sleep(config.VM_CHECK_FREQUENCY)

    def fix_broken_vm(self):
        for vm in self.pool.pool:
            vm.checking = True
            log.info("Checking {clone} with {ip}:{port}...".format(
                clone=vm.name, ip=vm.ip, port=config.SELENIUM_PORT))
            if vm.ready:
                if not vm.ping_vm():
                    try:
                        vm.rebuild()
                    except Exception as e:
                        log.error(e)
                        vm.delete()
                        self.pool.remove(vm)
            vm.checking = False

    def stop(self):
        self.running = False
        self.join(1)
        log.info("VMChecker stopped")


pool = VirtualMachinesPool()

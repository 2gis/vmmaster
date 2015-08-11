# coding: utf-8
from threading import Thread
from time import sleep

from vmmaster.core.logger import log


class DelayedVirtualMachine(object):
    def __init__(self, dc):
        self.dc = dc
        self.vm = None


class VMPoolQueue(list):
    def enqueue(self, desired_capabilities):
        log.info("Enqueue %s" % desired_capabilities)
        delayed_vm = DelayedVirtualMachine(desired_capabilities)
        self.append(delayed_vm)
        return delayed_vm

    def dequeue(self, item=None):
        index = 0
        if item:
            index = self.index(item)
        return self.pop(index)

    @property
    def info(self):
        res = list()
        for i in self:
            res.append(str(i.dc))
        return res


class QueueWorker(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.queue = queue

    def run(self):
        from vmpool.virtual_machines_pool import pool
        while self.running:
            for delayed_vm in list(self.queue):
                platform = delayed_vm.dc.get('platform', '')
                if pool.has(platform):
                    vm = pool.get_by_platform(platform)
                    self.queue.dequeue(delayed_vm)
                    delayed_vm.vm = vm
                elif pool.can_produce(platform):
                    vm = pool.add(platform)
                    self.queue.dequeue(delayed_vm)
                    delayed_vm.vm = vm
            sleep(0.1)

    def stop(self):
        self.running = False
        while self.queue:
            self.queue.dequeue()
        log.info("QueueWorker stopped")

q = VMPoolQueue()
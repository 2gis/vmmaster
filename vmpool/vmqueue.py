# coding: utf-8

from threading import Thread
from time import sleep

from core.logger import log
from vmpool.virtual_machines_pool import pool
from core.exceptions import QueueItemNotFound


class DelayedVirtualMachine(object):
    def __init__(self, dc):
        self.dc = dc
        self.vm = None

    def delete(self):
        log.info("Deleting request for getting vm from "
                 "queue with desired capabilities: %s" % self.dc)
        q.dequeue(self)


class VMPoolQueue(list):
    def enqueue(self, desired_capabilities):
        log.info("Enqueue %s" % desired_capabilities)
        delayed_vm = DelayedVirtualMachine(desired_capabilities)
        self.append(delayed_vm)
        return delayed_vm

    def dequeue(self, item=None):
        index = 0
        if item:
            try:
                index = self.index(item)
            except ValueError:
                raise QueueItemNotFound("Item %s not found" % item)
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
        while self.running:
            for delayed_vm in list(self.queue):
                platform = delayed_vm.dc.get('platform', '')
                vm = None
                if pool.has(platform):
                    vm = pool.get_by_platform(platform)
                elif pool.can_produce(platform):
                    vm = pool.add(platform)
                if vm:
                    try:
                        self.queue.dequeue(delayed_vm)
                    except QueueItemNotFound:
                        log.info(
                            "VM %s (%s) is no longer required" %
                            (vm.name, vm.ip)
                        )
                        vm.delete()
                    else:
                        delayed_vm.vm = vm
            sleep(0.1)

    def stop(self):
        self.running = False
        while self.queue:
            self.queue.dequeue()
        log.info("QueueWorker stopped")

q = VMPoolQueue()

# coding: utf-8
from threading import Thread
from time import sleep

from .virtual_machine.virtual_machines_pool import pool
from .logger import log


class DelayedVirtualMachine(object):
    def __init__(self, dc):
        self.dc = dc
        self.vm = None

    def to_json(self):
        return self.dc


class SessionQueue(list):
    def enqueue(self, desired_capabilities):
        log.info("Enqueue %s" % desired_capabilities)
        delayed_session = DelayedVirtualMachine(desired_capabilities)
        self.append(delayed_session)
        return delayed_session

    def dequeue(self, item=None):
        index = 0
        if item:
            index = self.index(item)
        return self.pop(index)


class QueueWorker(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            for delayed_vm in list(self.queue):
                platform = delayed_vm.dc.platform
                if pool.has(platform):
                    vm = pool.get(platform)
                    self.queue.dequeue(delayed_vm)
                    delayed_vm.vm = vm
                elif pool.can_produce():
                    vm = pool.add(platform)
                    self.queue.dequeue(delayed_vm)
                    delayed_vm.vm = vm
            sleep(0.1)

    def stop(self):
        self.running = False
        while self.queue:
            self.queue.dequeue()
        log.info("QueueWorker stopped")

q = SessionQueue()

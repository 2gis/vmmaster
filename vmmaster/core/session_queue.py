# coding: utf-8
from threading import Thread
from time import sleep

from .virtual_machine.virtual_machines_pool import pool
from .logger import log


class Job(object):
    _result = None

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return "Job: %s" % str(self.args)

    @property
    def result(self):
        return self._result

    def perform(self, *args, **kwargs):
        kwargs = self.kwargs.update(kwargs)
        if kwargs is None:
            kwargs = self.kwargs
        return self.func(*(self.args + args), **kwargs)


class SessionQueue(object):
    queue = list()

    def __len__(self):
        return len(self.queue)

    def __iter__(self):
        return iter(self.queue)

    def enqueue(self, job):
        log.info("Enqueue %s" % job)
        self.queue.append(job)
        return job

    def dequeue(self, item=None):
        index = 0
        if item:
            index = self.queue.index(item)
        return self.queue.pop(index)


def do_job(job, vm):
    result = job.perform(vm)
    job._result = result


class QueueWorker(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            for job in list(self.queue):
                req = job.args[1]
                if req.closed:
                    self.queue.dequeue(job)
                    continue
                platform = job.args[0]
                if pool.has(platform):
                    vm = pool.get(platform)
                    job = self.queue.dequeue(job)
                    t = Thread(target=do_job, args=(job, vm))
                    t.start()
                elif pool.can_produce():
                    pool.add(platform)
            sleep(0.1)

    def stop(self):
        self.running = False
        while self.queue.queue:
            self.queue.dequeue()

q = SessionQueue()

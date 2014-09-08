# coding: utf-8
from threading import Thread
from time import sleep

from redis import Redis
from rq import Queue

q = Queue(connection=Redis())


def do_job(job):
    result = job.perform()
    job._result = result
    job.save()


class Worker(Thread):
    def __init__(self, platforms):
        self.platforms = platforms
        Thread.__init__(self)
        self.running = False

    def run(self):
        while self.running:
            if not q.is_empty() and self.platforms.is_ready():
                job = q.dequeue()
                t = Thread(target=do_job, args=(job,))
                t.start()
            sleep(0.1)

    def stop(self):
        self.running = False
        while not q.is_empty():
            q.dequeue()
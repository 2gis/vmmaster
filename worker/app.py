# coding: utf-8

import logging
from uuid import uuid1
from muffin import Application
from worker.queue_consumer import BlockingQueueConsumer
from concurrent.futures import ThreadPoolExecutor


log = logging.getLogger(__name__)


class WorkerApp(Application):
    def __init__(self, *args, **kwargs):
        super(WorkerApp, self).__init__(*args, **kwargs)
        self.uuid = str(uuid1())
        self.executor = ThreadPoolExecutor(self.cfg.PARALLEL_PROCESSES)
        self.queue_consumer = BlockingQueueConsumer(app=self)


def create_app():
    return WorkerApp(
        'worker',
        CONFIG='worker.config.debug'
    )


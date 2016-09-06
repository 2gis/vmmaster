# coding: utf-8

import logging
from uuid import uuid1
from muffin import Application

from backend.queue_producer import AsyncQueueProducer
from backend.middlewares import request_check

log = logging.getLogger(__name__)


class BackendApp(Application):
    def __init__(self, *args, **kwargs):
        super(BackendApp, self).__init__(*args, **kwargs)
        self.uuid = str(uuid1())
        self.queue_producer = AsyncQueueProducer(app=self)
        self.sessions = {}

    async def start(self):
        await self.queue_producer.connect()
        await super(BackendApp, self).start()


def create_app():
    return BackendApp(
        'backend',
        CONFIG='backend.config.debug',
        middlewares=[request_check]
    )

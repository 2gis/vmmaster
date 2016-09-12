# coding: utf-8

import asyncio
import logging
from core import common, utils
from worker.queue_consumer import AsyncQueueConsumer
from worker.api import views as api_views


log = logging.getLogger(__name__)


class WorkerApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.queue_consumer = AsyncQueueConsumer(app=self)
        self.sessions = {}
        self.platforms = {}


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def create_app(loop=None):
    loop = asyncio.get_event_loop() if not loop else loop
    _app = WorkerApp(
        'worker',
        CONFIG='worker.config.debug',
        loop=loop
    )
    register_routes(_app, api_views, url_prefix='/api')
    asyncio.ensure_future(_app.queue_consumer.connect())
    return _app


app = create_app()

# coding: utf-8

import asyncio
import logging
import aiohttp_debugtoolbar
from core import common, utils
from worker.queue_consumer import AsyncQueueConsumer
from worker.api import views as api_views


log = logging.getLogger(__name__)


class WorkerApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.queue_consumer = AsyncQueueConsumer(app=self)
        self.sessions = {}
        self.platforms = {"ubuntu-14.04-x64": 1}


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def app(loop=None):
    loop = loop if loop else asyncio.get_event_loop()
    _app = WorkerApp(
        'worker',
        CONFIG='config.debug',
        loop=loop
    )
    if _app.cfg.DEBUG:
        aiohttp_debugtoolbar.setup(_app)
    register_routes(_app, api_views, url_prefix='/api')
    asyncio.ensure_future(_app.queue_consumer.connect(), loop=loop)
    return _app

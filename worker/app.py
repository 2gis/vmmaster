# coding: utf-8

import asyncio
import logging
import aiohttp_debugtoolbar
from uuid import uuid4
from core import common, utils, database
from worker.queue_consumer import AsyncQueueConsumer
from worker.api import views as api_views


log = logging.getLogger(__name__)


class WorkerApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.node = uuid4()
        self.queue_consumer = AsyncQueueConsumer(app=self)
        self.sessions = {}
        self.platforms = {"ubuntu-14.04-x64": 1}
        self.db = database.Database(app=self)


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def app(loop=None, CONFIG='settings'):
    loop = loop if loop else asyncio.get_event_loop()
    _app = WorkerApp(
        'worker',
        CONFIG=CONFIG,
        loop=loop
    )
    if _app.cfg.DEBUG:
        aiohttp_debugtoolbar.setup(_app)
    register_routes(_app, api_views, url_prefix='/api')
    asyncio.ensure_future(_app.queue_consumer.connect(), loop=loop)
    asyncio.ensure_future(_app.db.register_platforms(_app.node, _app.platforms), loop=loop)
    return _app

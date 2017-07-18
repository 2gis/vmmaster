# coding: utf-8

import asyncio
import logging
import logging.config
import aiohttp_debugtoolbar
from uuid import uuid4
from core import utils, common, database
from backend import middlewares
from backend.api import views as api_views
from backend.webdriver import views as selenium_views
from backend.queue_producer import AsyncQueueProducer


log = logging.getLogger(__name__)


class BackendApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.node = uuid4()
        self.db = database.Database(app=self)
        self.queue_producer = AsyncQueueProducer(app=self)
        self.sessions = {}
        # asyncio.ensure_future(self.db.register_platforms(self.node, {}))


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def app(loop=None, CONFIG='settings'):
    loop = loop if loop else asyncio.get_event_loop()
    _app = BackendApp(
        'backend',
        CONFIG=CONFIG,
        middlewares=[
            middlewares.request_middleware
        ],
        loop=loop
    )
    if _app.cfg.DEBUG:
        aiohttp_debugtoolbar.setup(_app)
    register_routes(_app, api_views, url_prefix='/api')
    register_routes(_app, selenium_views, url_prefix='/wd/hub')
    asyncio.ensure_future(_app.queue_producer.connect(), loop=loop)
    return _app

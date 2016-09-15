# coding: utf-8

import asyncio
import logging
import logging.config
import aiohttp_debugtoolbar
from core import utils, common
from backend.api import views as api_views
from backend.webdriver import views as selenium_views
from backend.queue_producer import AsyncQueueProducer
from backend.middlewares import request_check


log = logging.getLogger(__name__)


class BackendApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.queue_producer = AsyncQueueProducer(app=self)
        self.sessions = {}


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def app(loop=None):
    loop = loop if loop else asyncio.get_event_loop()
    _app = BackendApp(
        'backend',
        CONFIG='config.debug',
        middlewares=[request_check],
        loop=loop
    )
    if _app.cfg.DEBUG:
        aiohttp_debugtoolbar.setup(_app)
    register_routes(_app, api_views, url_prefix='/api')
    register_routes(_app, selenium_views, url_prefix='/wd/hub')
    asyncio.ensure_future(_app.queue_producer.connect(), loop=loop)
    return _app

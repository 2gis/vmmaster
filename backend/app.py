# coding: utf-8

import asyncio
import logging
import logging.config

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


def create_app(loop=None):
    loop = asyncio.get_event_loop() if not loop else loop
    _app = BackendApp(
        'backend',
        CONFIG='backend.config.debug',
        middlewares=[request_check],
        loop=loop
    )
    register_routes(_app, api_views, url_prefix='/api')
    register_routes(_app, selenium_views, url_prefix='/wd/hub')
    asyncio.ensure_future(_app.queue_producer.connect())
    return _app


app = create_app()
# if __name__ == "__main__":
#     loop = asyncio.get_event_loop()
#     app = create_app(loop=loop)
#     web.run_app(app, host=app.cfg.HOST, port=app.cfg.PORT)

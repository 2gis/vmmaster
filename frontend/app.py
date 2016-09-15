# coding: utf-8

import asyncio
import logging
from uuid import uuid1
from core import common, utils
from frontend import views as api_views


log = logging.getLogger(__name__)


class FrontendApp(common.BaseApplication):
    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(name=name, loop=loop, router=router, middlewares=middlewares, **OPTIONS)
        self.uuid = str(uuid1())


def register_routes(_app, views, url_prefix=None, name_prefix=None):
    with utils.add_route_context(_app, views, url_prefix=url_prefix, name_prefix=name_prefix) as route:
        for args in getattr(views, 'ROUTES', []):
            route(*args)


def create_app(loop=None):
    loop = asyncio.get_event_loop() if not loop else loop
    _app = FrontendApp(
        'frontend',
        CONFIG='config.debug',
        loop=loop
    )
    register_routes(_app, api_views, url_prefix='/api')
    return _app


app = create_app()

# coding: utf-8
import ujson
import logging
from aiohttp import web
from core import utils


log = logging.getLogger(__name__)
ROUTES = [
    ("GET", "/sessions", "get_sessions"),
    ("GET", "/messages", "get_messages")
]


async def get_sessions(request):
    return web.Response(
        body=utils.make_request_body(request.app.sessions),
        content_type='application/json',
        status=200
    )


async def get_messages(request):
    return web.Response(
        body=utils.make_request_body(request.app.queue_producer.messages),
        content_type='application/json',
        status=200
    )

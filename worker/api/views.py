# coding: utf-8
import ujson
import logging
from aiohttp import web


log = logging.getLogger(__name__)
ROUTES = [
    ("GET", "/sessions", "get_sessions"),
    ("GET", "/platforms", "get_platforms"),
    ("GET", "/messages", "get_messages"),
    ("GET", "/channels", "get_channels")
]


def make_request_body(data):
    return ujson.dumps(data).encode('utf-8')


async def get_sessions(request):
    return web.Response(
        body=make_request_body(request.app.sessions),
        content_type='application/json',
        status=200
    )


async def get_platforms(request):
    return web.Response(
        body=make_request_body(request.app.platforms),
        content_type='application/json',
        status=200
    )


async def get_messages(request):
    return web.Response(
        body=make_request_body(request.app.queue_consumer.messages),
        content_type='application/json',
        status=200
    )


async def get_channels(request):
    return web.Response(
        body=make_request_body(request.app.queue_consumer.channels),
        content_type='application/json',
        status=200
    )

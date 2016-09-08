# coding: utf-8
import ujson
import logging
from aiohttp import web


log = logging.getLogger(__name__)
ROUTES = [
    ("GET", "/sessions", "get_sessions"),
    ("GET", "/platforms", "get_platforms"),
    ("GET", "/sessions_messages", "get_sessions_messages"),
    ("GET", "/platforms_messages", "get_platforms_messages"),
    ("GET", "/service_messages", "get_service_messages")
]


def make_request_body(data):
    return ujson.dumps(data).encode('utf-8')


async def get_sessions(request):
    return web.Response(
        body=make_request_body(request.app.platforms),
        content_type='application/json',
        status=200
    )


async def get_platforms(request):
    return web.Response(
        body=make_request_body(request.app.platforms),
        content_type='application/json',
        status=200
    )


async def get_sessions_messages(request):
    return web.Response(
        body=make_request_body(request.app.queue_consumer.sessions_messages),
        content_type='application/json',
        status=200
    )


async def get_platforms_messages(request):
    return web.Response(
        body=make_request_body(request.app.queue_consumer.platforms_messages),
        content_type='application/json',
        status=200
    )


async def get_service_messages(request):
    return web.Response(
        body=make_request_body(request.app.queue_consumer.service_messages),
        content_type='application/json',
        status=200
    )

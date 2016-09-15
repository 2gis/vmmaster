# coding: utf-8

import ujson
import logging
from aiohttp import web
from core.exceptions import SessionException, PlatformException

log = logging.getLogger(__name__)


async def get_vmmaster_session(request):
    session_id = get_session_id(request.path)
    session = request.app.sessions.get(int(session_id))
    if not session:
        raise SessionException("Session %s not found" % session_id)


def form_response(code, headers, body):
    """ Send reply to client. """
    if not code:
        code = 500
        body = "Something ugly happened. No real reply formed."
        headers = {
            'Content-Length': len(body)
        }
    if isinstance(headers, str):
        headers = ujson.loads(headers)
    return web.Response(text=body, status=code, headers=headers)


def selenium_error_response(message, selenium_code=13, status_code=500):
    error_context = {
        'status': selenium_code,
        'value': {
            "message": "%s" % message
        }
    }
    error_context = ujson.dumps(error_context)
    return web.Response(text=error_context, content_type='application/json', status=status_code)


def check_platform(platform):
    if platform not in ["ubuntu-14.04-x64"]:
        raise PlatformException("Platform %s not found in available platforms")


async def get_platform(request):
    dc = await get_desired_capabilities(request)
    return dc.get('platform')


async def get_desired_capabilities(request):
    dc = None
    while not dc:
        body = await request.json(loads=ujson.loads)
        dc = body['desiredCapabilities']
    return dc


def get_session_id(path):
    parts = path.split("/")
    try:
        log.warn(parts)
        pos = parts.index("session")
        session_id = parts[pos + 1]
    except IndexError or ValueError:
        raise SessionException("In request path %s not found session id" % path)

    return session_id


def set_body_session_id(body, session_id):
    if body:
        body = ujson.loads(body)
        body["sessionId"] = session_id
        body = ujson.dumps(body)
    return body


def set_path_session_id(path, session_id):
    parts = path.split("/")
    pos = parts.index("session")
    parts[pos + 1] = str(session_id)
    return "/".join(parts)

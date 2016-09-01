# coding: utf-8

import ujson
import logging

from backend.sessions import Session
from core.exceptions import PlatformException, SessionException

log = logging.getLogger(__name__)


async def create_vmmaster_session(request):
    dc = await get_desired_capabilities(request)
    sessions_keys = list(request.app.sessions.keys())
    last_session_id = sessions_keys[-1] if sessions_keys else 0
    log.warn("Sessions %s, last id %s" % (request.app.sessions, last_session_id))
    session = Session(id=int(last_session_id)+1, dc=dc)
    request.app.sessions[session.id] = session
    log.info("New session %s (%s) for %s" % (str(session.id), session.name, str(dc)))
    return session


async def start_vmmaster_session(request, session):
    status, headers, body = await start_selenium_session(
        request, session, request.app.cfg.SELENIUM_PORT
    )

    log.warn("session: %s" % body)
    selenium_session = ujson.loads(body)["sessionId"]
    session.selenium_session = selenium_session
    session.save()

    body = set_body_session_id(body, session.id)
    headers = ujson.loads(headers)
    headers["Content-Length"] = len(body)

    return status, headers, body


async def start_selenium_session(request, session, port):
    status, headers, body = None, None, None

    log.info("Starting selenium-server-standalone session for %s" % session.id)
    log.debug("with %s %s %s %s" % (request.method, request.path, request.headers, request.content))

    if request.headers.get("Host"):
        headers = request.headers.copy()
        del headers['Host']

    parameters = ujson.dumps({
        "method": request.method,
        "port": port,
        "url": request.path,
        "headers": headers,
        "data": request.content
    })

    correlation_id = await request.app.queue_producer.add_msg_to_queue(session.platform, parameters)
    response = await request.app.queue_producer.get_message_from_queue(correlation_id)
    response = ujson.loads(response)
    return response.get('status'), response.get('headers', "{}"), response.get('content', "{}")


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

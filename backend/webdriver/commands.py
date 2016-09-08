# coding: utf-8

import ujson
import logging

from backend.sessions import Session
from backend.webdriver import helpers

log = logging.getLogger(__name__)


async def create_vmmaster_session(request):
    dc = await helpers.get_desired_capabilities(request)
    sessions_keys = list(request.app.sessions.keys())
    last_session_id = sessions_keys[-1] if sessions_keys else 0
    log.warn("Sessions %s, last id %s" % (request.app.sessions, last_session_id))
    session = Session(id=int(last_session_id)+1, dc=dc)
    log.info("New session %s (%s) for %s" % (str(session.id), session.name, str(dc)))
    request.app.sessions[session.id] = session
    await request.app.queue_producer.create_queue("vmmaster_session_%s" % session.id)
    return session


async def start_vmmaster_session(request, session):
    status, headers, body = await start_selenium_session(
        request, session, request.app.cfg.SELENIUM_PORT
    )

    selenium_session = ujson.loads(body)["sessionId"]
    session.selenium_session = selenium_session
    session.save()

    body = helpers.set_body_session_id(body, session.id)
    headers = ujson.loads(headers)
    headers["Content-Length"] = len(body)

    return status, headers, body


async def start_selenium_session(request, session, port):
    log.info("Starting selenium-server-standalone session for %s" % session.id)
    log.debug("with %s %s %s %s" % (request.method, request.path, request.headers, request.content))
    status, headers, body = await session.make_request(port, request, queue=session.platform)
    return status, headers, body


async def transparent(request, session):
    return await session.make_request(request.app.cfg.SELENIUM_PORT, request)


async def service_command_send(request, command):
    session_id = helpers.get_session_id(request.path)
    log.info("Sending service message for session %s" % session_id)
    parameters = {
        "platform": "ubuntu-14.04-x64",
        "sessionId": session_id,
        "command": command
    }
    parameters = ujson.dumps(parameters)
    return await request.app.queue_producer.add_msg_to_queue(request.app.cfg.RABBITMQ_COMMAND_QUEUE, parameters)


def vmmaster_agent(request, command):
    session = request.session
    return command(request, session)


def internal_exec(request, command):
    code, headers, body = command(request, request.session)
    return code, headers, body

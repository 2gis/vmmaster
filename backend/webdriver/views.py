# coding: utf-8

import logging
from backend.webdriver import helpers, commands


log = logging.getLogger(__name__)
ROUTES = [
    ("POST", "/session", "create_session"),
    ("DELETE", "/session/{session_id:\d+}", "delete_session"),
    ("GET", "session/{session_id:\d+}", "get_session"),
    ("GET", "session/{session_id:\d+}/{url:.*}", "get_proxy_request"),
    ("POST", "session/{session_id:\d+}/{url:.*}", "post_proxy_request"),
    ("DELETE", "session/{session_id:\d+}/{url:.*}", "delete_proxy_request"),
    ("POST", "session/{session_id:\d+}/vmmaster/runScript", "agent_command"),
    ("POST", "session/{session_id:\d+}/vmmaster/vmmasterLabel", "vmmaster_command")
]


async def create_session(request):
    session = await commands.create_vmmaster_session(request)
    status, headers, body = await commands.start_vmmaster_session(request, session)
    return helpers.form_response(status, headers, body)


async def delete_session(request):
    session_id = request.match_info.get("session_id")
    await commands.service_command_send(request, "SESSION_CLOSING")
    del request.app.sessions[int(session_id)]
    return helpers.form_response(200, {}, "Session %s closed" % session_id)


async def get_session(request):
    session_id = request.match_info.get("session_id")
    session = request.app.sessions[int(session_id)]
    return {"session": session}


async def get_proxy_request(request):
    session_id = request.match_info.get("session_id")
    session = request.app.sessions[int(session_id)]
    status, headers, body = await commands.transparent(request, session)
    return helpers.form_response(status, headers, body)


async def post_proxy_request(request):
    return await get_proxy_request(request)


async def delete_proxy_request(request):
    return await get_proxy_request(request)


async def agent_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "agent command %s" % session_id)


async def vmmaster_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "vmmaster command %s" % session_id)

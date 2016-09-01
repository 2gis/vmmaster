# coding: utf-8
import logging
from backend import app
from backend.webdriver import helpers, commands

BASE_URL = '/wd/hub'
log = logging.getLogger(__name__)


@app.register("%s/session" % BASE_URL, methods=["POST"])
async def create_session(request):
    session = await commands.create_vmmaster_session(request)
    status, headers, body = await commands.start_vmmaster_session(request, session)
    return helpers.form_response(status, headers, body)


@app.register(r"%s/session/{session_id:\d+}" % BASE_URL, methods=["DELETE"])
async def delete_session(request):
    session_id = request.match_info.get("session_id")
    session = request.app.sessions[int(session_id)]
    status, headers, body = await helpers.transparent(request, session)
    if status == 200:
        del request.app.sessions[int(session_id)]
    return helpers.form_response(status, helpers, body)


@app.register(r"%s/session/{session_id:\d+}" % BASE_URL, methods=["GET"])
async def get_session(request):
    session_id = request.match_info.get("session_id")
    session = request.app.sessions[int(session_id)]
    return {"session": session}


@app.register(r"%s/session/{session_id:\d+}/{url}" % BASE_URL, methods=["GET", "POST", "DELETE"])
async def proxy_request(request):
    session_id = request.match_info.get("session_id")
    session = request.app.sessions[int(session_id)]
    status, headers, body = await helpers.transparent(request, session)
    return helpers.form_response(status, headers, body)


@app.register(r"%s/session/{session_id:\d+}/vmmaster/runScript" % BASE_URL, methods=["POST"])
async def agent_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "agent command %s" % session_id)


@app.register(r"%s/session/{session_id:\d+}/vmmaster/vmmasterLabel" % BASE_URL, methods=["POST"])
async def vmmaster_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "vmmaster command %s" % session_id)

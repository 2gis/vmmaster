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


@app.register("%s/session/{session_id}" % BASE_URL, methods=["DELETE"])
async def delete_session(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "delete session %s" % session_id)


@app.register("%s/session/{session_id}" % BASE_URL, methods=["GET"])
async def get_session(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "{'success': 'get session %s'}" % session_id)


@app.register("%s/session/{session_id}/vmmaster/runScript" % BASE_URL, methods=["POST"])
async def agent_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "agent command %s" % session_id)


@app.register("%s/session/{session_id}/vmmaster/vmmasterLabel" % BASE_URL, methods=["POST"])
async def vmmaster_command(request):
    session_id = request.match_info.get("session_id")
    return helpers.form_response(200, {}, "vmmaster command %s" % session_id)


@app.register("%s/session/{session_id}/{url}" % BASE_URL, methods=["GET", "POST", "DELETE"])
async def proxy_request(request):
    session_id = request.match_info.get("session_id")
    url = request.match_info.get('url')
    return helpers.form_response(200, {}, "proxy request %s %s" % (session_id, url))

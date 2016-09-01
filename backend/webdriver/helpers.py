# coding: utf-8
import ujson
import logging
from muffin import Response

# from core.sessions import Session, RequestHelper
from core.exceptions import SessionException
from backend.webdriver import commands

log = logging.getLogger(__name__)


async def get_vmmaster_session(request):
    session_id = commands.get_session_id(request.path)
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

    return Response(text=body, status=code, headers=headers)


def selenium_error_response(message, selenium_code=13, status_code=500):
    error_context = {
        'status': selenium_code,
        'value': {
            "message": "%s" % message
        }
    }
    error_context = ujson.dumps(error_context)
    return Response(text=error_context, content_type='application/json', status=status_code)


def swap_session(req, desired_session):
    req.data = commands.set_body_session_id(req.data, desired_session)
    req.path = commands.set_path_session_id(req.path, desired_session)


async def transparent(request, session):
    # swap_session(request, request.session.selenium_session)
    status, headers, body = await session.make_request(request.app.cfg.SELENIUM_PORT, request)
    # swap_session(request, str(request.session.id))
    await status, headers, body


def vmmaster_agent(request, command):
    session = request.session
    swap_session(request, session.selenium_session)
    code, headers, body = command(request, session)
    swap_session(request, session.selenium_session)
    return code, headers, body


def internal_exec(request, command):
    code, headers, body = command(request, request.session)
    return code, headers, body

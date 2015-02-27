# coding: utf-8

import time
from traceback import format_exc

from flask import Blueprint, current_app, request, jsonify

from . import commands
import helpers


from ..core.db import database
from ..core.logger import log
from ..core.exceptions import SessionException, ConnectionError

webdriver = Blueprint('webdriver', __name__)


@webdriver.errorhandler(Exception)
def handle_errors(error):
    tb = format_exc()
    log.error(tb)
    if request.proxy.session_id:
        try:
            session = current_app.sessions.get_session(request.proxy.session_id)
        except SessionException:
            pass
        else:
            session.failed(tb)
    error_context = {
        'status': 1,
        'value': "%s" % tb
    }
    return jsonify(error_context), 500


@webdriver.before_request
def log_request():
    log.info(request)
    request.proxy = helpers.SessionProxy()
    proxy = request.proxy
    req = request.proxy.request
    if proxy.session_id:
        session = current_app.sessions.get_session(proxy.session_id)
        session.vmmaster_log_step = helpers.write_vmmaster_log(
            proxy.session_id, "%s %s %s" % (req.method, req.path, req.clientproto), str(req.body))


def send_response(response):
    if request.proxy.request.closed:
        raise ConnectionError("Session closed by user")
    return response


@webdriver.after_request
def log_response(response):
    proxy = request.proxy
    helpers.write_vmmaster_log(proxy.session_id, response.status_code, response.data)
    return response


@webdriver.route('/session/<session_id>', methods=['DELETE'])
@helpers.threaded
def delete_session(session_id):
    proxy = request.proxy
    proxy.response = helpers.transparent(proxy)
    current_app.sessions.get_session(proxy.session_id).succeed()
    return send_response(proxy.response)


@webdriver.route('/session', methods=['POST'])
@helpers.threaded
def create_session():
    req = request.proxy.request
    proxy = request.proxy
    desired_caps = commands.get_desired_capabilities(req)
    session = helpers.get_session(desired_caps)
    proxy.session_id = session.id
    session.vmmaster_log_step = helpers.write_vmmaster_log(
        proxy.session_id, "%s %s %s" % (req.method, req.path, req.clientproto), str(req.body))
    status, headers, body = commands.start_session(req, session)
    proxy.response = helpers.form_response(status, headers, body)
    return send_response(proxy.response)


@webdriver.route("/session/<path:url>", methods=['GET', 'POST', 'DELETE'])
@helpers.threaded
def proxy_request(url):
    req = request.proxy.request
    proxy = request.proxy
    last = url.split("/")[-1]
    if last in commands.AgentCommands:
        proxy.response = helpers.vmmaster_agent(commands.AgentCommands[last], proxy)
    elif last in commands.InternalCommands:
        proxy.response = helpers.internal_exec(commands.InternalCommands[last], proxy)
    else:
        proxy.response = helpers.transparent(proxy)

    words = ["url", "click", "execute", "keys", "value"]
    parts = req.path.split("/")

    session = current_app.sessions.get_session(proxy.session_id)
    if session.vmmaster_log_step:
        screenshot = None
        if set(words) & set(parts) or parts[-1] == "session":
            screenshot = helpers.take_screenshot(proxy)
        if screenshot:
            session.vmmaster_log_step.screenshot = screenshot
            database.update(session.vmmaster_log_step)

    return send_response(proxy.response)
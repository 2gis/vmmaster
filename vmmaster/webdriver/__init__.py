# coding: utf-8

from traceback import format_exc
from flask import Blueprint, current_app, request, jsonify, abort

from vmmaster.webdriver import commands
import helpers
from vmmaster.core.db import database
from vmmaster.core.logger import log
from vmmaster.core.exceptions import SessionException, ConnectionError
from vmmaster.core.auth.custom_auth import auth, anonymous

webdriver = Blueprint('webdriver', __name__)


@webdriver.errorhandler(Exception)
def handle_errors(error):
    tb = format_exc()
    log.error(tb)
    if request.proxy.session_id:
        try:
            session = current_app.sessions.get_session(
                request.proxy.session_id)
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
    log.debug('%s' % request)

    if current_app.running is False:
        log.info("This request is aborted %s" % request)
        abort(502)
    else:
        request.proxy = helpers.SessionProxy()
        proxy = request.proxy
        req = request.proxy.request

        if proxy.session_id:
            session = current_app.sessions.get_session(proxy.session_id)
            session.add_session_step(
                "%s %s %s" % (req.method, req.path, req.clientproto),
                str(req.body))


def send_response(response):
    if request.proxy.request.closed:
        raise ConnectionError("Session closed by user")
    return response


@webdriver.after_request
def log_response(response):
    proxy = request.proxy
    try:
        session = current_app.sessions.get_session(proxy.session_id)
    except SessionException:
        session = None
    if session:
        session.add_session_step(response.status_code, response.data)
    log.debug('Response %s %s' % (response.data, response.status_code))
    return response


@auth.get_password
def get_token(username):
    if username == anonymous.username:
        return anonymous.password
    else:
        return database.get_user(username=username).token


@auth.verify_password
def verify_token(username, client_token):
    return client_token == get_token(username)


@webdriver.route('/session/<session_id>', methods=['DELETE'])
@helpers.threaded
def delete_session(session_id):
    proxy = request.proxy
    proxy.response = helpers.transparent(proxy)
    session = current_app.sessions.get_session(proxy.session_id)
    session.add_session_step(proxy.response.status_code, proxy.response.data)
    session.succeed()
    return send_response(proxy.response)


@webdriver.route('/session', methods=['POST'])
@auth.login_required
@helpers.threaded
def create_session():
    req = request.proxy.request
    proxy = request.proxy

    session = helpers.get_session(req)
    proxy.session_id = session.id

    session.add_session_step(
        "%s %s %s" % (req.method, req.path, req.clientproto),
        str(req.body))

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
        proxy.response = helpers.vmmaster_agent(
            commands.AgentCommands[last], proxy)
    elif last in commands.InternalCommands:
        proxy.response = helpers.internal_exec(
            commands.InternalCommands[last], proxy)
    else:
        proxy.response = helpers.transparent(proxy)

    words = ["url", "click", "execute", "keys", "value"]
    parts = req.path.split("/")

    session = current_app.sessions.get_session(proxy.session_id)
    if session.log_step:
        screenshot = None
        if set(words) & set(parts) or parts[-1] == "session":
            screenshot = helpers.take_screenshot(proxy)
        if screenshot:
            session.log_step.screenshot = screenshot
            session.log_step.save()
    return send_response(proxy.response)

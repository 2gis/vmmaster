# coding: utf-8

from traceback import format_exc
from flask import Blueprint, current_app, request, jsonify, abort

from vmmaster.webdriver import commands
import helpers

from core.logger import log
from core.exceptions import SessionException, ConnectionError
from core.auth.custom_auth import auth, anonymous
from core import utils

webdriver = Blueprint('webdriver', __name__)


@webdriver.errorhandler(Exception)
def handle_errors(error):
    tb = format_exc()
    log.error(tb)
    if request.session_id:
        try:
            session = current_app.sessions.get_session(
                request.session_id)
        except SessionException:
            pass
        else:
            session.failed(tb)

    error_context = {
        'status': 13,
        'value': {
            "message": "%s" % tb
        }
    }
    return jsonify(error_context), 500


@webdriver.before_request
def log_request():
    log.debug('%s' % request)

    session_id = commands.get_session_id(request.path)
    request.session_id = session_id

    if session_id:
        session = current_app.sessions.get_session(session_id)
        control_line = "%s %s %s" % (
            request.method, request.path,
            request.headers.environ['SERVER_PROTOCOL']
        )
        session.add_session_step(control_line=control_line,
                                 body=str(request.data))


def send_response(response):
    if helpers.is_request_closed():
        raise ConnectionError("Session closed by user")
    return response


@webdriver.after_request
def log_response(response):
    session_id = request.session_id

    if session_id:
        try:
            session = current_app.sessions.get_session(session_id)
        except SessionException:
            session = None
        if session:
            response_data = utils.remove_base64_screenshot(response.data)
            session.add_session_step(control_line=response.status_code,
                                     body=response_data,
                                     milestone=False)
    log.debug('Response %s %s' % (response.data, response.status_code))
    return response


@auth.get_password
def get_token(username):
    if username == anonymous.username:
        return anonymous.password
    else:
        return current_app.database.get_user(username=username).token


@auth.verify_password
def verify_token(username, client_token):
    return client_token == get_token(username)


@webdriver.route('/session/<session_id>', methods=['DELETE'])
@helpers.threaded
def delete_session(session_id):
    request.response = helpers.transparent()
    response = request.response

    request.session_id = session_id
    session = current_app.sessions.get_session(request.session_id)
    session.add_session_step(control_line=response.status_code,
                             body=request.response.data,
                             milestone=False)
    session.succeed()

    # Session is done, forget about it
    request.session_id = None
    return send_response(response)


@webdriver.route('/session', methods=['POST'])
@auth.login_required
@helpers.threaded
def create_session():
    if current_app.running:
        session = helpers.get_session()
        control_line = "%s %s %s" % (
            request.method, request.path,
            request.headers.environ['SERVER_PROTOCOL']
        )
        session.add_session_step(control_line=control_line,
                                 body=str(request.data))

        status, headers, body = commands.start_session(request, session)
        request.response = helpers.form_response(status, headers, body)
        return send_response(request.response)
    else:
        log.info("This request is aborted %s" % request)
        abort(502)


@webdriver.route("/session/<path:url>", methods=['GET', 'POST', 'DELETE'])
@helpers.threaded
def proxy_request(url):
    request.session_id = url.split("/")[0]

    last = url.split("/")[-1]
    if last in commands.AgentCommands:
        request.response = helpers.vmmaster_agent(
            commands.AgentCommands[last])
    elif last in commands.InternalCommands:
        request.response = helpers.internal_exec(
            commands.InternalCommands[last])
    else:
        request.response = helpers.transparent()

    words = ["url", "click", "execute", "keys", "value"]
    only_screenshots = ["element", "execute_async"]
    parts = request.path.split("/")
    session_id = request.session_id
    session = current_app.sessions.get_session(session_id)
    if set(words) & set(parts) or parts[-1] == "session":
        utils.to_thread(helpers.save_screenshot(session))
    elif set(only_screenshots) & set(parts) \
            and request.response.status_code == 500:
        utils.to_thread(helpers.save_screenshot(session))

    return send_response(request.response)

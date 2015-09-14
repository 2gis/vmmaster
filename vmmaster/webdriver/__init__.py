# coding: utf-8

from traceback import format_exc
from flask import Blueprint, current_app, request, jsonify, abort

from vmmaster.webdriver import commands
import helpers

from core.logger import log
from core.exceptions import SessionException
from core.auth.custom_auth import auth, anonymous
from core import utils

webdriver = Blueprint('webdriver', __name__)


@webdriver.errorhandler(Exception)
def handle_errors(error):
    tb = format_exc()
    log.error(tb)
        # try:
            #
        # except SessionException:
            # pass
        # else:
    request.session.failed(tb)

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
@helpers.response_generator
def delete_session(session_id):
    request.session = current_app.sessions.get_session(session_id)
    for status, headers, body in helpers.transparent():
        yield status, headers, body

    request.session_id = session_id
    session = current_app.sessions.get_session(request.session_id)
    session.add_session_step(control_line=status,
                             body=body,
                             milestone=False)
    session.succeed()

    # Session is done, forget about it
    request.session_id = None
    yield helpers.form_response(status, headers, body)


@webdriver.route('/session', methods=['POST'])
@auth.login_required
@helpers.response_generator
def create_session():
    if current_app.running:
        session_generator = helpers.get_session()
        session = next(session_generator)
        request.session = session
        request.session_id = session.id
        for session in session_generator:
            yield session
        control_line = "%s %s %s" % (
            request.method, request.path,
            request.headers.environ['SERVER_PROTOCOL']
        )
        session.add_session_step(control_line=control_line,
                                 body=str(request.data))


        commands.replace_platform_with_any(request)
        for status, headers, body in commands.start_session(request, session):
            yield status, headers, body
        yield helpers.form_response(status, headers, body)
    else:
        log.info("This request is aborted %s" % request)
        abort(502)


@webdriver.route("/session/<session_id>/<path:url>", methods=['GET', 'POST', 'DELETE'])
@helpers.response_generator
def proxy_request(session_id, url):
    request.session = current_app.sessions.get_session(session_id)
    last = url.split("/")[-1]
    if last in commands.AgentCommands:
        status, headers, body = helpers.vmmaster_agent(
            commands.AgentCommands[last])
    elif last in commands.InternalCommands:
        status, headers, body = helpers.internal_exec(
            commands.InternalCommands[last])
    else:
        for status, headers, body in helpers.transparent():
            yield status, headers, body

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
        if session.take_screenshot:
            helpers.take_screenshot(request.session)

    yield helpers.form_response(status, headers, body)

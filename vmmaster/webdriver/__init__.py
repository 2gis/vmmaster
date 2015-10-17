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
    if hasattr(request, 'session'):
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

    try:
        session = current_app.sessions.get_session(session_id)
    except SessionException:
        session = None

    if session:
        control_line = "%s %s %s" % (
            request.method, request.path,
            request.headers.environ['SERVER_PROTOCOL']
        )
        session.add_session_step(
            control_line=control_line,
            body=str(request.data)
        )


@webdriver.after_request
def log_response(response):
    log.debug('Response %s %s' % (response.data, response.status_code))

    if hasattr(request, 'session'):
        session = request.session
        response_data = utils.remove_base64_screenshot(response.data)
        session.add_session_step(control_line=response.status_code,
                                 body=response_data)
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
def delete_session(session_id):
    request.session = current_app.sessions.get_session(session_id)
    status, headers, body = helpers.transparent()

    request.session.add_session_step(
        control_line=status, body=body
    )
    request.session.succeed()

    del request.session
    return helpers.form_response(status, headers, body)


@webdriver.route('/session', methods=['POST'])
@auth.login_required
def create_session():
    if current_app.running:
        session = helpers.get_session()
        commands.replace_platform_with_any(request)
        status, headers, body = commands.start_session(request, session)
        return helpers.form_response(status, headers, body)
    else:
        log.info("This request is aborted %s" % request)
        abort(502)


@webdriver.route("/session/<string:session_id>", methods=['GET'])
def get_session(session_id):
    request.session = current_app.sessions.get_session(session_id)
    status, headers, body = helpers.transparent()
    return helpers.form_response(status, headers, body)


def take_screenshot(status, body):
    words = ["url", "click", "execute", "keys", "value"]
    only_screenshots = ["element", "execute_async"]
    parts = request.path.split("/")
    if set(words) & set(parts) or parts[-1] == "session":
        utils.to_thread(
            helpers.take_screenshot_from_session(request.session))
    elif set(only_screenshots) & set(parts) and status == 500:
        utils.to_thread(
            helpers.take_screenshot_from_response(request.session, body))


@webdriver.route(
    "/session/<string:session_id>/vmmaster/runScript", methods=['POST']
)
def agent_command(session_id):
    request.session = current_app.sessions.get_session(session_id)

    status, headers, body = helpers.vmmaster_agent(
        commands.AgentCommands['runScript'])

    take_screenshot(status, body)
    return helpers.form_response(status, headers, body)


@webdriver.route(
    "/session/<string:session_id>/vmmaster/vmmasterLabel", methods=['POST']
)
def vmmaster_command(session_id):
    request.session = current_app.sessions.get_session(session_id)

    status, headers, body = helpers.internal_exec(
        commands.InternalCommands['vmmasterLabel'])

    take_screenshot(status, body)
    return helpers.form_response(status, headers, body)


@webdriver.route("/session/<string:session_id>/<path:url>",
                 methods=['GET', 'POST', 'DELETE'])
def proxy_request(session_id, url=None):
    request.session = current_app.sessions.get_session(session_id)

    status, headers, body = helpers.transparent()

    take_screenshot(status, body)
    return helpers.form_response(status, headers, body)

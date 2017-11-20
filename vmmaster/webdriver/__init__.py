# coding: utf-8
from time import sleep
import logging
from datetime import datetime
from traceback import format_exc
from flask import Blueprint, current_app, request, jsonify, g, Response

from vmmaster.webdriver import commands, helpers

from core.exceptions import SessionException
from core.auth.custom_auth import auth
from core import utils
from core.profiler import profiler

webdriver = Blueprint('webdriver', __name__)
log = logging.getLogger(__name__)


def selenium_error_response(message, selenium_code=13, status_code=500):
    log.info('selenium_error_response: {} {} {}'.format(message, selenium_code, status_code))
    error_context = {
        'status': selenium_code,
        'value': {
            "message": "%s" % message
        }
    }
    log.warning(error_context)
    res = jsonify(error_context), status_code
    log.warning(res)
    return res


@webdriver.errorhandler(Exception)
def handle_errors(error):
    log.exception('ERROR HANDLER: {}'.format(error))
    # sleep(2)
    tb = format_exc()
    if hasattr(request, 'session') and not request.session.closed:
        request.session.failed(tb=tb, reason=error)

    log.warning('RESPONDING!')
    # sleep(2)
    # helpers.form_response(status, headers, body)
    return selenium_error_response("%s %s" % (error, tb), status_code=500)


def get_vmmaster_session(request):
    if hasattr(request, 'session'):
        session = request.session
        session.refresh()
    else:
        session_id = commands.get_session_id(request.path)

        try:
            session = current_app.sessions.get_session(session_id)
        except SessionException:
            session = None

    return session


def log_request(session, request, created=None):
    control_line = "%s %s %s" % (
        request.method, request.path,
        request.headers.environ['SERVER_PROTOCOL']
    )
    session.add_session_step(
        control_line=control_line,
        body=str(request.data),
        created=created
    )


@webdriver.before_request
def before_request():
    g.started = datetime.now()
    log.debug('%s' % request)
    session = get_vmmaster_session(request)

    if session:
        session.stop_timer()
        log_request(session, request, created=g.started)


def log_response(session, response, created=None):
    response_data = utils.remove_base64_screenshot(response.data)
    session.add_session_step(control_line=response.status_code,
                             body=response_data, created=created)


@webdriver.after_request
def after_request(response):
    log.debug('Response %s %s' % (response.data, response.status_code))
    session = get_vmmaster_session(request)
    parts = request.path.split("/")

    if session:
        log_response(session, response, created=datetime.now())
        if not session.closed:
            if request.method == 'DELETE' and parts[-2] == "session" \
                    and parts[-1] == str(session.id):
                session.succeed()
            else:
                session.start_timer()

    return response


@webdriver.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    request.session = current_app.sessions.get_session(session_id)
    status, headers, body = helpers.transparent()
    return helpers.form_response(status, headers, body)


@webdriver.route('/session', methods=['POST'])
@auth.login_required
def create_session():
    if not current_app.running:
        log.info("This request is aborted %s" % request)
        message = "A new session could not be created " \
                  "because shutdown server in progress"
        return selenium_error_response(message, status_code=502)

    with profiler.requests_duration(create_session.__name__):
        session = helpers.get_session()
        log_request(session, request, created=g.started)  # because session id required for step
        commands.replace_platform_with_any(request)
        status, headers, body = commands.start_session(request, session)

        return helpers.form_response(status, headers, body)


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

    return helpers.form_response(status, headers, body)


@webdriver.route("/session/<string:session_id>/<path:url>",
                 methods=['GET', 'POST', 'DELETE'])
def proxy_request(session_id, url=None):
    request.session = current_app.sessions.get_session(session_id)

    status, headers, body = helpers.transparent()

    take_screenshot(status, body)
    return helpers.form_response(status, headers, body)

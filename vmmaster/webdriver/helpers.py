# coding: utf-8

import base64
import commands
import json
import time
import logging

from PIL import Image
from functools import wraps
from flask import Response, request, current_app

from core.exceptions import CreationException, ConnectionError, TimeoutException, SessionException
from core.config import config

from core import constants
from core import utils
from core.utils.network_utils import RequestHelper
from core.profiler import profiler
from core.sessions import Session
from vmpool import endpoint


log = logging.getLogger(__name__)


def is_request_closed():
    if getattr(request.input_stream, "_wrapped", None):
        return request.input_stream._wrapped.closed
    else:
        return request.input_stream.closed


def is_session_timeouted():
    if hasattr(request, 'session') and request.session.timeouted:
        return "Session %s timeout (%s)" % \
               (request.session.id, request.session.reason)
    return None


def is_session_closed():
    if hasattr(request, 'session') and request.session.closed:
        return "Session %s closed (%s)" % \
               (request.session.id, request.session.reason)
    return None


def connection_watcher(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for value in func(*args, **kwargs):
            session_timeouted = is_session_timeouted()
            session_closed = is_session_closed()

            if is_request_closed():
                raise ConnectionError("Client has disconnected")
            elif session_timeouted:
                raise TimeoutException(session_timeouted)
            elif session_closed:
                raise SessionException(session_closed)

            time.sleep(0.01)
        return value
    return wrapper


def save_screenshot(session, screenshot):
    if screenshot:
        log_step = session.current_log_step
        path = config.SCREENSHOTS_DIR + "/" + str(session.id) + \
            "/" + str(log_step.id) + ".png"
        utils.write_file(path, base64.b64decode(screenshot))
        log_step.screenshot = path
        log_step.save()
        make_thumbnail_for_screenshot(path)


def take_screenshot_from_response(session, body):
    data = json.loads(body)
    try:
        screenshot = data.get('value', {}).get('screen', None)
    except AttributeError:
        log.debug('Screenshot not found in webdriver '
                  'response for session %s' % session.id)
        screenshot = None

    save_screenshot(session, screenshot)


def take_screenshot_from_session(session):
    if session.take_screenshot:
        for screenshot in commands.take_screenshot(session):
            pass
    else:
        screenshot = None

    save_screenshot(session, screenshot)


def make_thumbnail_for_screenshot(screenshot_path):
    screenshot_resize(screenshot_path, 128, postfix="_thumb")


def screenshot_resize(screenshot_path, width, height=None, postfix=None):
    try:
        img = Image.open(screenshot_path)

        if height:
            size = width, height
        else:
            wpercent = (width / float(img.size[0]))
            size = width, int((float(img.size[1]) * float(wpercent)))

        if postfix:
            postfix = "%s.png" % postfix
        else:
            postfix = "%sx%s.png" % size

        new_file_path = screenshot_path.split('.png')[0] + postfix
        img = img.resize(size, Image.ANTIALIAS)
        img.save(new_file_path, "PNG")
    except IOError:
        log.debug("Can\'t resize image '%s'" % screenshot_path)


def form_response(code, headers, body):
    """ Send reply to client. """
    if not code:
        code = 500
        body = "Something ugly happened. No real reply formed."
        headers = {
            'Content-Length': len(body)
        }
    return Response(response=body, status=code, headers=headers.iteritems())


def swap_session(req, desired_session):
    req.data = commands.set_body_session_id(req.data, desired_session)
    req.path = commands.set_path_session_id(req.path, desired_session)


@connection_watcher
def transparent():
    status, headers, body = None, None, None
    swap_session(request, request.session.selenium_session)
    for status, headers, body in request.session.make_request(
        request.session.endpoint.selenium_port,
        RequestHelper(
            request.method, request.path, request.headers, request.data
        )
    ):
        yield status, headers, body

    swap_session(request, str(request.session.id))
    yield status, headers, body


def vmmaster_agent(command):
    session = request.session
    swap_session(request, session.selenium_session)
    code, headers, body = command(request, session)
    swap_session(request, session.selenium_session)
    return code, headers, body


def internal_exec(command):
    code, headers, body = command(request, request.session)
    return code, headers, body


def check_to_exist_ip(session, tries=10, timeout=5):
    i = 0
    while True:
        if session.endpoint.ip is not None:
            return session.endpoint.ip
        else:
            if i > tries:
                raise CreationException('Error: VM %s have not ip address' %
                                        session.endpoint.name)
            i += 1
            log.info('IP is %s for VM %s, wait for %ss. before next try...' %
                     (session.endpoint.ip, session.endpoint.name, timeout))
            time.sleep(timeout)


def get_endpoint(session_id, dc):
    _endpoint = None
    attempt = 0
    attempts = getattr(config, "GET_ENDPOINT_ATTEMPTS",
                       constants.GET_ENDPOINT_ATTEMPTS)
    wait_time = 0
    wait_time_increment = getattr(config, "GET_ENDPOINT_WAIT_TIME_INCREMENT",
                                  constants.GET_ENDPOINT_WAIT_TIME_INCREMENT)

    while not _endpoint:
        attempt += 1
        wait_time += wait_time_increment
        try:
            log.info("Try to get endpoint for session %s. Attempt %s" % (session_id, attempt))
            for vm in endpoint.get_vm(dc):
                _endpoint = vm
                yield _endpoint
            profiler.register_success_get_endpoint(attempt)
            log.info("Attempt %s to get endpoint %s for session %s was succeed"
                     % (attempt, _endpoint, session_id))
        except CreationException as e:
            log.exception("Attempt %s to get endpoint for session %s was failed: %s"
                          % (attempt, session_id, str(e)))
            if _endpoint and not _endpoint.ready:
                _endpoint.delete()
                _endpoint = None
            if attempt < attempts:
                time.sleep(wait_time)
            else:
                profiler.register_fail_get_endpoint()
                raise e

    yield _endpoint


@connection_watcher
def get_session():
    profiler.register_get_session_call()

    dc = commands.get_desired_capabilities(request)
    if not current_app.match(dc):
        raise SessionException("Cannot match platform for DesiredCapabilities: {}".format(dc))

    session = Session(dc=dc)
    request.session = session
    log.info("New session %s (%s) for %s" % (str(session.id), session.name, str(dc)))
    yield session

    for _endpoint in get_endpoint(session.id, dc):
        if _endpoint:
            session.refresh()
            session.endpoint_id = _endpoint.id
            session.endpoint = _endpoint
            session.save()
        yield session

    session.run()
    yield session

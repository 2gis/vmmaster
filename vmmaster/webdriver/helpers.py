# coding: utf-8

import base64
import sys
import commands

from functools import wraps
from threading import Thread
from Queue import Queue

from flask import Response, current_app, request, copy_current_request_context

from core.exceptions import ConnectionError, \
    CreationException, PlatformException
from core.config import config
from core.logger import log
from core.utils import utils
from core import endpoints
from core.sessions import Session


class BucketThread(Thread):
    def __init__(self, bucket, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.bucket = bucket

    def run(self):
        try:
            super(BucketThread, self).run()
        except:
            self.bucket.put(sys.exc_info())


def is_request_closed():
    return request.input_stream._wrapped.closed


def threaded(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        @copy_current_request_context
        def thread_target():
            return func(*args, **kwargs)

        error_bucket = Queue()
        tr = BucketThread(target=thread_target, bucket=error_bucket)
        tr.daemon = True
        tr.start()

        while tr.isAlive() and not is_request_closed():
            tr.join(0.1)

        if is_request_closed():
            if request.session_id:
                session = current_app.sessions.get_session(request.session_id)
                session.failed()
            raise ConnectionError("Client has disconnected")
        elif not error_bucket.empty():
            error = error_bucket.get()
            raise error[0], error[1], error[2]

        return request.response

    return wrapper


def take_screenshot(session):
    screenshot = commands.take_screenshot(session, config.VMMASTER_AGENT_PORT)
    if screenshot:
        log_step = session.get_milestone_step()
        path = config.SCREENSHOTS_DIR + "/" + str(session.id) + \
            "/" + str(log_step.id) + ".png"
        utils.write_file(path, base64.b64decode(screenshot))
        log_step.screenshot = screenshot


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


def transparent():
    from core.sessions import RequestHelper

    session = current_app.sessions.get_session(request.session_id)
    swap_session(request, session.selenium_session)
    code, headers, response_body = session.make_request(
        config.SELENIUM_PORT,
        RequestHelper(
            request.method, request.path, request.headers, request.data
        )
    )

    swap_session(request, request.session_id)
    return form_response(code, headers, response_body)


def vmmaster_agent(command):
    session = current_app.sessions.get_session(request.session_id)
    swap_session(request, session.selenium_session)
    code, headers, body = command(request, session)
    swap_session(request, session.selenium_session)
    return form_response(code, headers, body)


def internal_exec(command):
    session = current_app.sessions.get_session(request.session_id)
    code, headers, body = command(request, session)
    return form_response(code, headers, body)


def check_to_exist_ip(session, tries=10, timeout=5):
    from time import sleep
    i = 0
    while True:
        if session.endpoint_ip is not None:
            return session.endpoint_ip
        else:
            if i > tries:
                raise CreationException('Error: VM %s have not ip address' %
                                        session.endpoint_name)
            i += 1
            log.info('IP is %s for VM %s, wait for %ss. before next try...' %
                     (session.endpoint_ip, session.endpoint_name, timeout))
            sleep(timeout)


def get_session():
    dc = commands.get_desired_capabilities(request)
    commands.replace_platform_with_any(request)

    session = Session(dc=dc)
    request.session_id = session.id
    log.info("New session %s (%s) for %s" %
             (str(session.id), session.name, str(dc)))

    try:
        endpoint = endpoints.get(dc)
    except Exception as e:
        error_message = '%s' % str(e.message)
        session.failed(error_message)
        raise PlatformException(error_message)

    if is_request_closed() or session.is_closed():
        if endpoint:
            endpoints.delete(endpoint["id"])
        raise ConnectionError(
            "Session was closed during creating selenium session"
        )

    session.run(endpoint)
    return session

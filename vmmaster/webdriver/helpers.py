# coding: utf-8

import base64
import sys
import commands

from functools import wraps
from threading import Thread
from Queue import Queue

from flask import Request as FlaskRequest
from flask import Response, current_app, request, copy_current_request_context

from vmmaster.core.exceptions import ConnectionError, \
    CreationException, PlatformException, TimeoutException
from vmmaster.core.config import config
from vmmaster.core.logger import log
from vmmaster.core.utils import utils


class BucketThread(Thread):
    def __init__(self, bucket, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)
        self.bucket = bucket

    def run(self):
        try:
            super(BucketThread, self).run()
        except:
            self.bucket.put(sys.exc_info())


def threaded(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        @copy_current_request_context
        def thread_target():
            return func(*args, **kwargs)

        proxy = request.proxy
        req = proxy.request
        error_bucket = Queue()
        tr = BucketThread(target=thread_target, bucket=error_bucket)
        tr.daemon = True
        tr.start()

        while tr.isAlive() and not req.closed:
            tr.join(0.1)

        if req.closed:
            if proxy.session_id:
                session = current_app.sessions.get_session(proxy.session_id)
                session.failed()
            raise ConnectionError("Client has disconnected")
        elif not error_bucket.empty():
            error = error_bucket.get()
            raise error[0], error[1], error[2]

        return proxy.response

    return wrapper


class Request(FlaskRequest):
    def __init__(self):
        super(Request, self).__init__(request.environ)
        self.clientproto = self.headers.environ['SERVER_PROTOCOL']
        headers = {}
        for key, value in self.headers.items():
            if value:
                headers[key] = value
        self.headers = headers
        self.body = self.data

    def __str__(self):
        return "%s %s %s" % (self.method, self.url, self.body)

    @property
    def closed(self):
        return self.input_stream._wrapped.closed


class SessionProxy(object):
    def __init__(self):
        self.request = Request()
        self.response = None
        self._session_id = None

    @property
    def session_id(self):
        if not self._session_id:
            self._session_id = commands.get_session_id(self.request.path)
        return self._session_id

    @session_id.setter
    def session_id(self, value):
        self._session_id = value


def take_screenshot(proxy):
    session = current_app.sessions.get_session(proxy.session_id)
    if not session.take_screenshot:
        return None

    screenshot = commands.take_screenshot(session, 9000)

    if screenshot:
        log_step = session.get_milestone_step()
        path = config.SCREENSHOTS_DIR + "/" + str(proxy.session_id) + \
            "/" + str(log_step.id) + ".png"
        utils.write_file(path, base64.b64decode(screenshot))
        return path


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
    req.body = commands.set_body_session_id(req.body, desired_session)
    req.path = commands.set_path_session_id(req.path, desired_session)
    if req.body:
        req.headers['Content-Length'] = len(req.body)


def transparent(proxy):
    from vmmaster.core.sessions import RequestHelper

    req = proxy.request
    session = current_app.sessions.get_session(proxy.session_id)
    swap_session(req, session.selenium_session)
    code, headers, response_body = session.make_request(
        config.SELENIUM_PORT,
        RequestHelper(req.method, req.path, req.headers, req.body)
    )

    swap_session(req, proxy.session_id)
    return form_response(code, headers, response_body)


def vmmaster_agent(command, proxy):
    req = proxy.request
    session = current_app.sessions.get_session(proxy.session_id)
    swap_session(req, session.selenium_session)
    code, headers, body = command(req, session)
    swap_session(req, session.selenium_session)
    return form_response(code, headers, body)


def internal_exec(command, proxy):
    session = current_app.sessions.get_session(proxy.session_id)
    code, headers, body = command(proxy.request, session)
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


def get_session(req):
    from vmmaster.core import endpoints

    dc = commands.get_desired_capabilities(req)
    commands.replace_platform_with_any(req)

    from vmmaster.core.sessions import Session
    session = Session(dc=dc)

    try:
        endpoint = endpoints.get(dc)
    except Exception as e:
        error_message = '%s' % str(e.message)
        session.failed(error_message)
        raise PlatformException(error_message)

    session.run(endpoint)
    return session

# coding: utf-8

import json
import httplib
from functools import partial, wraps
import websocket
import logging

from traceback import format_exc
from core import utils, constants
from core.utils import network_utils
from core.utils import generator_wait_for

from vmmaster.webdriver.helpers import check_to_exist_ip, connection_watcher

from core.config import config
from core.exceptions import CreationException
from core.sessions import update_log_step

from threading import Thread
from flask import copy_current_request_context

log = logging.getLogger(__name__)


def add_sub_step(session, func):
    @wraps(func)
    def wrapper(port, request, *args, **kwargs):
        session.add_sub_step(
            control_line="%s %s" % (request.method, request.url),
            body=request.data)

        try:
            for status, headers, body in func(port, request, *args, **kwargs):
                yield status, headers, body
        except Exception as e:
            session.add_sub_step(
                control_line='500',
                body=format_exc()
            )
            raise e
        else:
            content_to_log = utils.remove_base64_screenshot(body) if body else None

            session.add_sub_step(
                control_line=str(status),
                body=content_to_log)

            yield status, headers, body

    return wrapper


@connection_watcher
def start_session(request, session):
    log.info("Start preparing selenium session for {}".format(session))
    status, headers, body = None, None, None

    ping_endpoint_before_start_session(session, session.endpoint.bind_ports)
    yield status, headers, body

    selenium_status(request, session)
    yield status, headers, body

    if session.run_script:
        startup_script(session)

    status, headers, body = start_selenium_session(
        request, session
    )

    json_body = utils.to_json(body)
    if json_body.get("sessionId"):
        selenium_session = json_body.get("sessionId")
    elif json_body.get("value", {}).get("sessionId"):
        selenium_session = json_body.get("value").get("sessionId")
    else:
        raise CreationException("SessionId not found in selenium response {}".format(json_body))

    log.debug('Selenium real session_id {} for session {}'.format(selenium_session, session.id))
    session.refresh()
    session.selenium_session = selenium_session
    session.save()

    body = set_body_session_id(body, session.id)
    headers["Content-Length"] = len(body)

    yield status, headers, body


def startup_script(session):
    if not session.endpoint.agent_port:
        log.debug("Run user script was skipped because endpoint have not AGENT PORT")
        return
    r = network_utils.RequestHelper(method="POST", data=session.run_script)
    status, headers, body = run_script(r, session)
    if status != httplib.OK:
        raise Exception("failed to run script: %s" % body)
    script_result = json.loads(body)
    if script_result.get("status") != 0:
        raise Exception("failed to run script with code %s:\n%s" % (
            script_result.get("status"), script_result.get("output")))


@connection_watcher
def ping_endpoint_before_start_session(session, ports):
    ip = check_to_exist_ip(session)

    log.info("Starting ping: {ip}:{ports}".format(ip=ip, ports=str(ports)))
    _ping = partial(network_utils.ping, ip)

    def check():
        return all(map(_ping, ports))
    for _ in generator_wait_for(check, config.PING_TIMEOUT):
        yield False

    result = map(_ping, ports)
    if not all(result):
        fails = [port for port, res in zip(ports, result) if res is False]
        raise CreationException("Failed to ping ports %s" % str(fails))

    if session.closed:
        raise CreationException("Session was closed while ping")

    log.info("Ping successful: {ip}:{ports}".format(ip=ip, ports=str(ports)))

    yield True


@connection_watcher
def start_selenium_session(request, session):
    status, headers, body = None, None, None

    log.info("Starting selenium-server-standalone session for {}".format(session.id))
    log.debug("with %s %s %s %s" % (request.method, request.path,
                                    request.headers, request.data))

    wrapped_make_request = add_sub_step(session, session.make_request)
    for status, headers, body in wrapped_make_request(
        session.endpoint.selenium_port, network_utils.RequestHelper(
            request.method, request.path, request.headers, request.data
        ), timeout=constants.CREATE_SESSION_REQUEST_TIMEOUT
    ):
        yield status, headers, body

    if status != httplib.OK:
        log.info("FAILED start selenium-server-standalone status "
                 "for %s - %s : %s" % (session.id, status, body))
        raise CreationException("Failed to start selenium session: %s" % body)

    log.info("SUCCESS start selenium-server-standalone session for {}".format(session.id))
    yield status, headers, body


@connection_watcher
def selenium_status(request, session):
    parts = request.path.split("/")
    parts[-1] = "status"
    status_cmd = "/".join(parts)
    status, headers, body, selenium_status_code = None, None, None, None

    log.info("Getting selenium-server-standalone status for {}".format(session))

    wrapped_make_request = add_sub_step(session, session.make_request)
    for status, headers, body in wrapped_make_request(
        session.endpoint.selenium_port, network_utils.RequestHelper("GET", status_cmd)
    ):
        yield status, headers, body
    selenium_status_code = json.loads(body).get("status", None)

    if selenium_status_code != 0:
        log.info("FAILED get selenium-server-standalone status for {}".format(session))
        raise CreationException("Failed to get selenium status: %s" % body)

    log.info("SUCCESS get selenium-server-standalone status for {}".format(session))
    yield status, headers, body


# TODO: make a decorator
def replace_platform_with_any(request):
    body = json.loads(request.data)
    desired_capabilities = body["desiredCapabilities"]

    desired_capabilities["platform"] = constants.ANY
    body["desiredCapabilities"] = desired_capabilities

    request.data = json.dumps(body)


def get_desired_capabilities(request):
    return utils.get_desired_capabilities(request.data)


def get_session_id(path):
    parts = path.split("/")
    try:
        pos = parts.index("session")
    except ValueError:
        return None
    try:
        session_id = parts[pos + 1]
    except IndexError:
        return None

    return session_id


def set_body_session_id(body, session_id):
    if not body:
        return body

    body = json.loads(body)
    body["sessionId"] = session_id
    return json.dumps(body)


def set_path_session_id(path, session_id):
    parts = path.split("/")
    pos = parts.index("session")
    parts[pos + 1] = str(session_id)
    return "/".join(parts)


def take_screenshot(session):
    if not session.endpoint.agent_port:
        log.debug("Take screenshot was skipped because endpoint have not AGENT PORT")
        return
    for status, headers, body in session.make_request(
        session.endpoint.agent_port,
        network_utils.RequestHelper(method="GET", url="/takeScreenshot")
    ):
        pass

    if status == httplib.OK and body:
        json_response = json.loads(body)
        return json_response.get("screenshot", None)


@connection_watcher
def run_script_through_websocket(script, session, host):
    status_code = 200
    default_msg = json.dumps({"status": 0, "output": ""})
    sub_step = session.add_sub_step(
        control_line=status_code,
        body=default_msg)

    def on_open(_ws):
        def run():
            _ws.send(script)
            log.info('RunScript: Open websocket and send message %s '
                     'to vmmaster-agent on vm %s' % (script, host))
        _t = Thread(target=run)
        _t.daemon = True
        _t.start()

    def on_message(_ws, message):
        _ws.output += message
        if sub_step:
            msg = json.dumps({"status": _ws.status, "output": _ws.output})
            update_log_step(sub_step, message=msg)

    def on_close(_ws):
        if sub_step and ws.output:
            msg = json.dumps({"status": _ws.status, "output": _ws.output})
            update_log_step(sub_step, message=msg)
        log.info("RunScript: Close websocket on vm %s" % host)

    def on_error(_ws, message):
        global status_code
        status_code = 500
        _ws.status = 1
        _ws.output += repr(message)
        log.debug("RunScript error: %s" % message)

    ws = websocket.WebSocketApp(host,
                                on_message=on_message,
                                on_close=on_close,
                                on_open=on_open,
                                on_error=on_error)
    ws.output = ""
    ws.status = 0
    session.ws = ws

    t = Thread(target=copy_current_request_context(ws.run_forever))
    t.daemon = True
    t.start()

    while t.isAlive():
        yield None, None, None

    full_msg = json.dumps({"status": ws.status, "output": ws.output})
    yield status_code, {}, full_msg


def run_script(request, session):
    host = "ws://%s:%s/runScript" % (session.endpoint.ip, session.endpoint.agent_port)

    session.add_sub_step(
        control_line="%s %s" % (request.method, '/runScript'),
        body=request.data)

    return run_script_through_websocket(request.data, session, host)


def vmmaster_label(request, session):
    json_body = json.loads(request.data)
    return 200, {}, json.dumps({"sessionId": session.id, "status": 0,
                                "value": json_body["label"],
                                "labelId": 1})


AgentCommands = {
    "runScript": run_script
}

InternalCommands = {
    "vmmasterLabel": vmmaster_label,
}

# coding: utf-8

import json
import httplib
import time
from functools import partial
import websocket
import thread

from ..core.utils import network_utils
from ..webdriver.helpers import check_to_exist_ip
from ..core.config import config
from ..core.logger import log
from ..core.exceptions import CreationException
from ..core.sessions import RequestHelper, write_session_log, \
    update_data_in_obj
from ..core.utils.graphite import graphite, send_metrics
from ..core.auth.custom_auth import anonymous


class DesiredCapabilities(object):
    def __init__(self,
                 name=None,
                 platform=None,
                 takeScreenshot=None,
                 runScript=None,
                 user=None,
                 token=None):
        self.name = name
        self.platform = platform
        self.takeScreenshot = bool(takeScreenshot)
        self.runScript = dict(runScript)
        self.user = user
        self.token = token

    def to_json(self):
        return {
            "name": self.name,
            "platform": self.platform,
            "takeScreenshot": self.takeScreenshot,
            "runScript": self.runScript,
            "user": self.user,
            "token": self.token
        }

    def __repr__(self):
        return "<DesiredCapabilities name=%s platform=%s>" % (self.name,
                                                              self.platform)


def start_session(request, session):
    notdot_platform = "".join(session.platform.split("."))
    _start = time.time()

    graphite("%s.%s" % (notdot_platform, "ping_vm"))(ping_vm)(session)
    graphite("%s.%s" % (notdot_platform, "selenium_status"))(selenium_status)(
        request, session, config.SELENIUM_PORT)

    if session.desired_capabilities.runScript:
        startup_script(session)

    status, headers, body = graphite("%s.%s" % (
        notdot_platform, "start_selenium_session"))(
            start_selenium_session)(request, session, config.SELENIUM_PORT)

    selenium_session = json.loads(body)["sessionId"]
    session.selenium_session = selenium_session
    body = set_body_session_id(body, session.id)
    headers["Content-Length"] = len(body)

    send_metrics("%s.%s" % (notdot_platform, "creation_total"),
                 time.time() - _start)
    return status, headers, body


def startup_script(session):
    r = RequestHelper(method="POST", body=json.dumps(
        session.desired_capabilities.runScript))
    status, headers, body = run_script(r, session)
    if status != httplib.OK:
        raise Exception("failed to run script: %s" % body)
    script_result = json.loads(body)
    if script_result.get("status") != 0:
        raise Exception("failed to run script with code %s:\n%s" % (
            script_result.get("status"), script_result.get("output")))


def ping_vm(session):
    ip = check_to_exist_ip(session.virtual_machine)
    ports = [config.SELENIUM_PORT, config.VMMASTER_AGENT_PORT]
    timeout = config.PING_TIMEOUT

    log.info("Starting ping: {ip}:{ports}".format(ip=ip, ports=str(ports)))
    _ping = partial(network_utils.ping, ip)
    start = time.time()
    while time.time() - start < timeout and not session.closed:
        session.timer.restart()
        result = map(_ping, ports)
        if all(result):
            break
        time.sleep(0.1)

    result = map(_ping, ports)
    if not all(result):
        fails = [port for port, res in zip(ports, result) if res is False]
        raise CreationException("Failed to ping ports %s" % str(fails))

    if session.closed:
        raise CreationException("Session was closed while ping")

    log.info("Ping successful: {ip}:{ports}".format(ip=ip, ports=str(ports)))

    return True


def start_selenium_session(request, session, port):
    status, headers, body = None, None, None

    for attempt_start in range(3):
        if session.closed:
            raise CreationException(
                "Session was closed while during starting selenium")

        log.info(
            "Attempt %s. Starting selenium-server-standalone session for %s" %
            (attempt_start, session.id))
        log.info("with %s %s %s %s" % (request.method, request.path,
                                       request.headers, request.body))

        status, headers, body = session.make_request(
            port,
            RequestHelper(request.method, request.path,
                          request.headers, request.body))
        if status == httplib.OK:
            log.info("SUCCESS start selenium-server-standalone status for %s" %
                     session.id)
            break
        else:
            log.info("Attempt %s to start selenium session was FAILED. "
                     "Trying again..." % attempt_start)

    if status != httplib.OK:
        log.info("FAILED start selenium-server-standalone status "
                 "for %s - %s : %s" % (session.id, status, body))
        raise CreationException("Failed to start selenium session: %s" % body)
    return status, headers, body


def selenium_status(request, session, port):
    parts = request.path.split("/")
    parts[-1] = "status"
    status_cmd = "/".join(parts)
    status, headers, body, selenium_status_code = None, None, None, None

    for attempt in range(3):
        if session.closed:
            raise CreationException(
                "Session was closed while before getting selenium status")

        log.info("Attempt %s. Getting selenium-server-standalone status "
                 "for %s" % (attempt, session.id))

        status, headers, body = session.make_request(
            port, RequestHelper("GET", status_cmd))
        selenium_status_code = json.loads(body).get("status", None)

        if selenium_status_code == 0:
            log.info("SUCCESS get selenium-server-standalone status for %s" %
                     session.id)
            break
        else:
            log.info("Attempt %s to get selenium status was FAILED. "
                     "Trying again..." % attempt)

    if selenium_status_code != 0:
        log.info("FAIL get selenium-server-standalone status for %s" %
                 session.id)
        raise CreationException("Failed to get selenium status: %s" % body)
    return status, headers, body


def replace_platform_with_any(request):
        body = json.loads(request.body)
        desired_capabilities = body["desiredCapabilities"]

        desired_capabilities["platform"] = u"ANY"
        body["desiredCapabilities"] = desired_capabilities

        new_body = json.dumps(body)
        request.body = new_body
        request.headers["Content-Length"] = len(request.body)


def get_desired_capabilities(request):
    body = json.loads(request.body)

    replace_platform_with_any(request)
    dc = DesiredCapabilities(
        body['desiredCapabilities'].get('name', None),
        body['desiredCapabilities'].get('platform', None),
        body['desiredCapabilities'].get('takeScreenshot', None),
        body['desiredCapabilities'].get('runScript', dict()),
        body['desiredCapabilities'].get('user', anonymous.username),
        body['desiredCapabilities'].get('token', anonymous.password)
    )
    return dc


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
    parts[pos + 1] = session_id
    return "/".join(parts)


def take_screenshot(session, port):
    status, headers, body = session.make_request(
        port, RequestHelper(method="GET", url="/takeScreenshot", headers={},
                            body=""))
    if status == httplib.OK and body:
        json_response = json.loads(body)
        return json_response["screenshot"]
    else:
        return None


def run_script_through_websocket(request, session, host):
    status_code = 200
    full_msg = json.dumps({"status": 0, "output": ''})

    if session.vmmaster_log_step:
        log_step = write_session_log(
            session.vmmaster_log_step.id, status_code, full_msg)

    def on_open(ws):
        def run(*args):
            ws.send(request.body)
            log.info('RunScript: Open websocket and send message %s '
                     'to vmmaster-agent on vm %s' % (request.body, host))
        thread.start_new_thread(run, ())

    def on_message(ws, message):
        ws.output += message
        if session.vmmaster_log_step:
            full_msg = json.dumps({"status": 0, "output": ws.output})
            update_data_in_obj(log_step, message=full_msg)

    def on_close(ws):
        log.info("RunScript: Close websocket on vm %s" % host)
        if session.vmmaster_log_step:
            full_msg = json.dumps({"status": 1, "output": ws.output})
            update_data_in_obj(log_step, message=full_msg)

    def on_error(ws, message):
        # status_code = 500
        ws.output = message
        log.debug("RunScript error: %s" % message)

    ws = websocket.WebSocketApp(host,
                                on_message=on_message,
                                on_close=on_close,
                                on_open=on_open,
                                on_error=on_error)
    ws.output = ""
    ws.run_forever()

    return status_code, {}, full_msg


def run_script(request, session):
    host = "ws://%s:%s/runScript" % (session.virtual_machine.ip,
                                     config.VMMASTER_AGENT_PORT)

    if session.vmmaster_log_step:
        write_session_log(session.vmmaster_log_step.id, "%s %s" %
                          (request.method, '/runScript'), request.body)

    return run_script_through_websocket(request, session, host)


def vmmaster_label(request, session):
    json_body = json.loads(request.body)
    return 200, {}, json.dumps({"sessionId": session.id, "status": 0,
                                "value": json_body["label"]})


def reserve_session():
    pass


AgentCommands = {
    "runScript": run_script
}

InternalCommands = {
    "vmmasterLabel": vmmaster_label,
    "reserveSession": reserve_session,
    "startSession": vmmaster_label,
}

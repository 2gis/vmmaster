import json
import httplib
import time

from flask import Request

from ..core.utils import network_utils
from ..webdriver.helpers import check_to_exist_ip
from ..core.config import config
from ..core.logger import log
from ..core.exceptions import CreationException
from ..core.sessions import RequestHelper
from ..core.utils.graphite import graphite, send_metrics


class DesiredCapabilities(object):
    def __init__(self, name, platform, takeScreenshot, runScript):
        self.name = name
        self.platform = platform
        self.takeScreenshot = bool(takeScreenshot)
        self.runScript = dict(runScript)

    def to_json(self):
        return {
            "name": self.name,
            "platform": self.platform,
            "takeScreenshot": self.takeScreenshot,
            "runScript": self.runScript,
        }

    def __repr__(self):
        return "<DesiredCapabilities name=%s platform=%s>" % (self.name, self.platform)


def start_session(request, session):
    notdot_platform = "".join(session.platform.split("."))
    _start = time.time()

    graphite("%s.%s" % (notdot_platform, "ping_vm"))(ping_vm)(session)
    graphite("%s.%s" % (notdot_platform, "selenium_status"))(selenium_status)(request, session, config.SELENIUM_PORT)

    if session.desired_capabilities.runScript:
        startup_script(session)

    status, headers, body = graphite("%s.%s" % (notdot_platform, "start_selenium_session"))(start_selenium_session)(request, session, config.SELENIUM_PORT)

    selenium_session = json.loads(body)["sessionId"]
    session.selenium_session = selenium_session
    body = set_body_session_id(body, session.id)
    headers["Content-Length"] = len(body)

    send_metrics("%s.%s" % (notdot_platform, "creation_total"), time.time() - _start)
    return status, headers, body


def startup_script(session):
    r = RequestHelper(method="POST", body=json.dumps(session.desired_capabilities.runScript))
    status, headers, body = run_script(r, session)
    if status != httplib.OK:
        raise Exception("failed to run script: %s" % body)
    script_result = json.loads(body)
    if script_result.get("status") != 0:
        raise Exception("failed to run script with code %s:\n%s" % (
            script_result.get("status"), script_result.get("output")))


def ping_vm(session):
    # ping ip:port
    ip = check_to_exist_ip(session.virtual_machine)
    port = config.SELENIUM_PORT
    timeout = config.PING_TIMEOUT
    start = time.time()
    log.info("Starting ping: {ip}:{port}".format(ip=ip, port=port))
    while time.time() - start < timeout and not session.closed:
        session.timer.restart()
        if network_utils.ping(ip, port):
            break
        time.sleep(0.1)

    if session.closed:
        raise CreationException("Session was closed while ping")

    if not network_utils.ping(ip, port):
        raise CreationException("Ping timeout")

    log.info("Ping successful: {ip}:{port}".format(ip=ip, port=port))

    return True


def start_selenium_session(request, session, port):
    status, headers, body = None, None, None

    for attempt_start in range(3):
        if session.closed:
            raise CreationException("Session was closed while during starting selenium")

        log.info("Attempt %s. Starting selenium-server-standalone session for %s" % (attempt_start, session.id))
        log.info("with %s %s %s %s" % (request.method, request.path, request.headers, request.body))

        status, headers, body = session.make_request(port, RequestHelper(request.method, request.path, request.headers, request.body))
        if status == httplib.OK:
            log.info("SUCCESS start selenium-server-standalone status for %s" % session.id)
            break
        else:
            log.info("Attempt %s to start selenium session was FAILED. Trying again..." % attempt_start)

    if status != httplib.OK:
        log.info("FAILED start selenium-server-standalone status for %s - %s : %s" % (session.id, status, body))
        raise CreationException("Failed to start selenium session: %s" % body)
    return status, headers, body


def selenium_status(request, session, port):
    parts = request.path.split("/")
    parts[-1] = "status"
    status_cmd = "/".join(parts)
    status, headers, body, selenium_status_code = None, None, None, None

    for attempt in range(3):
        if session.closed:
            raise CreationException("Session was closed while before getting selenium status")

        log.info("Attempt %s. Getting selenium-server-standalone status for %s" % (attempt, session.id))

        status, headers, body = session.make_request(port, RequestHelper("GET", status_cmd))
        selenium_status_code = json.loads(body).get("status", None)

        if selenium_status_code == 0:
            log.info("SUCCESS get selenium-server-standalone status for %s" % session.id)
            break
        else:
            log.info("Attempt %s to get selenium status was FAILED. Trying again..." % attempt)

    if selenium_status_code != 0:
        log.info("FAIL get selenium-server-standalone status for %s" % session.id)
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
        body['desiredCapabilities'].get('runScript', dict())
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
        port, RequestHelper(method="GET", url="/takeScreenshot", headers={}, body=""))
    if status == httplib.OK and body:
        json_response = json.loads(body)
        return json_response["screenshot"]
    else:
        return None


def run_script(request, session):
    return session.make_request(
        config.VMMASTER_AGENT_PORT, RequestHelper(
            method=request.method, url="/runScript",
            headers=request.headers, body=request.body))


def vmmaster_label(request, session):
    json_body = json.loads(request.body)
    return 200, {}, json.dumps({"sessionId": session.id, "status": 0, "value": json_body["label"]})


def reserve_session():
    pass


# def start_session():
#     pass


AgentCommands = {
    "runScript": run_script
}

InternalCommands = {
    "vmmasterLabel": vmmaster_label,
    "reserveSession": reserve_session,
    "startSession": vmmaster_label,
}
import json
import httplib
import time

from .utils import network_utils
from .config import config
from .logger import log
from .exceptions import CreationException
from .sessions import RequestHelper
from .utils.graphite import graphite, send_metrics


class DesiredCapabilities(object):
    def __init__(self, name, platform, takeScreenshot):
        self.name = name
        self.platform = platform
        self.takeScreenshot = bool(takeScreenshot)


def create_session(sessions, desired_caps):
    session = sessions.start_session(desired_caps.name, desired_caps.platform)
    return session


def start_session(request, session, platforms):
    notdot_platform = "".join(session.platform.split("."))
    _start = time.time()
    vm = graphite("%s.%s" % (notdot_platform, "create"))(platforms.create)(session.platform, session.id)
    session.virtual_machine = vm

    status = graphite("%s.%s" % (notdot_platform, "ping_vm"))(ping_vm)(session)
    if session.closed:
        return 500, {}, "Session closed by user"

    if not status:
        log.info("ping failed: TIMEOUT. Session: %s".format(session.id))
        raise CreationException("failed to ping virtual machine")

    # check status
    if not graphite("%s.%s" % (notdot_platform, "selenium_status"))(selenium_status)(request, session, config.SELENIUM_PORT):
        if session.timeouted:
            return 500, {}, "failed to get status of selenium-server-standalone"
        else:
            raise CreationException("failed to get status of selenium-server-standalone")

    response = graphite("%s.%s" % (notdot_platform, "start_selenium_session"))(start_selenium_session)(request, session, config.SELENIUM_PORT)
    status, headers, body = response
    send_metrics("%s.%s" % (notdot_platform, "creation_total"), time.time() - _start)

    if status == httplib.OK:
        selenium_session = json.loads(body)["sessionId"]
        session.selenium_session = selenium_session
        body = set_body_session_id(body, session.id)
        headers["Content-Length"] = len(body)

    return status, headers, body


def ping_vm(session):
    # ping ip:port
    ip = session.virtual_machine.ip
    port = config.SELENIUM_PORT
    timeout = config.PING_TIMEOUT
    start = time.time()
    log.info("starting ping: {ip}:{port}".format(ip=ip, port=port))
    while time.time() - start < timeout and not session.closed:
        session.timer.restart()
        if network_utils.ping(ip, port):
            break
        time.sleep(0.1)

    if session.closed:
        return False

    if not network_utils.ping(ip, port):
        return False

    log.info("ping successful: {ip}:{port}".format(ip=ip, port=port))

    return True


def start_selenium_session(request, session, port):
    status = None
    headers = None
    body = None
    for attempt in range(3):
        log.info("ATTEMPT %s start selenium-server-standalone session for %s" % (attempt, session.id))
        log.info("with %s %s %s %s" % (request.method, request.path, request.headers, request.body))
        status, headers, body = session.make_request(port, RequestHelper(request.method, request.path, request.headers, request.body))
        if status == httplib.OK:
            log.info("SUCCESS start selenium-server-standalone session for %s" % session.id)
            return status, headers, body

        # need to read response to keep sending requests
        log.info("FAILED start selenium-server-standalone session for %s - %s : %s" % (session.id, status, body))

    return status, headers, body


def selenium_status(request, session, port):
    parts = request.path.split("/")
    parts[-1] = "status"
    status = "/".join(parts)

    log.info("getting selenium-server-standalone status for %s" % session.id)
    # try to get status for 3 times
    for check in range(3):
        code, headers, body = session.make_request(port, RequestHelper("GET", status))
        if code == httplib.OK:
            log.info("SUCCESS get selenium-server-standalone status for %s" % session.id)
            return True
        else:
            log.info("FAIL    get selenium-server-standalone status for %s" % session.id)

    return False


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
        body['desiredCapabilities'].get('takeScreenshot', None)
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

import json
import httplib
import time

from .utils import network_utils
from .config import config
from .logger import log
from .db import database
from .exceptions import StatusException
from .sessions import RequestHelper


def delete_session(self):
    self.transparent("DELETE")
    self.sessions.get_session(self.session_id).succeed()


def create_session(self):
    name = get_session_name(self) if get_session_name(self) else None
    self.session = self.sessions.start_session(name)
    self.session_id = str(self.session.id)

    self._log_step = database.createLogStep(
        session_id=self.session_id,
        control_line="%s %s %s" % (self.method, self.path, self.clientproto),
        body=str(self.body),
        time=time.time())

    platform = get_platform(self)
    replace_platform_with_any(self)
    clone = self.clone_factory.create_clone(platform)
    self.session.clone = clone
    self.session.clone_factory = self.clone_factory

    # ping ip:port
    network_utils.ping(self.session, config.SELENIUM_PORT, config.PING_TIMEOUT)

    # check status
    if not selenium_status(self, self.session, config.SELENIUM_PORT):
        raise StatusException("failed to get status of selenium-server-standalone")

    status, headers, body = start_selenium_session(self, self.session, config.SELENIUM_PORT)

    selenium_session = json.loads(body)["sessionId"]
    self.session.selenium_session = selenium_session
    body = set_body_session_id(body, self.session_id)
    headers["content-length"] = len(body)

    self.form_reply(status, headers, body)


def start_selenium_session(self, session, port):
    # try to get status for 3 times
    status = None
    headers = None
    body = None
    for check in range(3):
        status, headers, body = session.make_request(port, RequestHelper(self.method, self.path, self.headers, self.body))
        if status == httplib.OK:
            log.debug("SUCCESS start selenium-server-standalone session for %s" % session.id)
            return status, headers, body

        # need to read response to keep sending requests
        log.info("FAILED start selenium-server-standalone session for %s - %s : %s" % (session.id, status, body))

    return status, headers, body


def selenium_status(self, session, port):
    parts = self.path.split("/")
    parts[-1] = "status"
    status = "/".join(parts)

    # try to get status for 3 times
    for check in range(3):
        code, headers, body = session.make_request(port, RequestHelper("get", status))
        if code == httplib.OK:
            log.debug("SUCCESS get selenium-server-standalone status for %s" % session.id)
            return True
        else:
            log.debug("FAIL    get selenium-server-standalone status for %s" % session.id)

    return False


def replace_platform_with_any(self):
    body = json.loads(self.body)
    desired_capabilities = body["desiredCapabilities"]

    desired_capabilities["platform"] = u"ANY"
    body["desiredCapabilities"] = desired_capabilities

    new_body = json.dumps(body)
    self.body = new_body
    self.headers["content-length"] = len(self.body)


def get_desired_capabilities(self):
    body = json.loads(self.body)
    return body["desiredCapabilities"]


def get_platform(self):
    return get_desired_capabilities(self)["platform"]


def get_session_name(self):
    try:
        return get_desired_capabilities(self)["name"]
    except KeyError:
        return None


def get_session_id(path):
    parts = path.split("/")
    pos = parts.index("session")
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


def take_screenshot(ip, port):
    conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))
    conn.request(method="GET", url="/takeScreenshot", headers={}, body="")
    response = conn.getresponse()
    if response.status == httplib.OK:
        json_response = json.loads(response.read())
        conn.close()
        return json_response["screenshot"]
    else:
        conn.close()
        return None

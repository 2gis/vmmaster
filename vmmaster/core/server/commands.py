import json
import httplib
import time

from vmmaster.utils import network_utils
from vmmaster.core.config import config
from vmmaster.core.logger import log


class StatusException(Exception):
    pass


def delete_session(self):
    self.transparent("DELETE")
    clone = self.sessions.get_clone(self.session_id)
    self.clone_factory.utilize_clone(clone)
    session = self.database.getSession(self.session_id)
    session.status = "succeed"
    self.database.update(session)


def create_session(self):
    name = get_session_name(self) if get_session_name(self) else None
    # db related stuff
    session = self.database.createSession(status="running", name=name, time=time.time())
    self.session_id = str(session.id)

    self._log_step = self.database.createLogStep(
        session_id=self.session_id,
        control_line="%s %s %s" % (self.method, self.path, self.clientproto),
        body=str(self.body),
        time=time.time())

    platform = get_platform(self)
    replace_platform_with_any(self)
    clone = self.clone_factory.create_clone(platform)

    # ping ip:port
    network_utils.ping(clone.get_ip(), config.SELENIUM_PORT, config.PING_TIMEOUT)

    # check status
    if not selenium_status(self, clone.get_ip(), config.SELENIUM_PORT):
        self.clone_factory.utilize_clone(clone)
        ### @todo: every exception got to be sent back to client
        raise StatusException("failed to get status of selenium-server-standalone")

    response = session_response(self, clone.get_ip(), config.SELENIUM_PORT)

    if response.status != httplib.OK:
        self.clone_factory.utilize_clone(clone)
        raise StatusException("failed to start selenium session")

    if response.getheader('Content-Length') is None:
        response_body = None
    else:
        content_length = int(response.getheader('Content-Length'))
        response_body = response.read(content_length)

    selenium_session = json.loads(response_body)["sessionId"]
    self.sessions.add_session(self.session_id, clone, selenium_session)
    response_body = set_body_session_id(response_body, self.session_id)
    headers = dict(x for x in response.getheaders())
    headers["content-length"] = len(response_body)

    self.form_reply(response.status, headers, response_body)


def session_response(self, ip, port):
    conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))

    conn.request(method="POST", url=self.path, headers=self.headers, body=self.body)
    # try to get status for 3 times
    for check in range(3):
        response = conn.getresponse()
        if response.status == httplib.OK:
            log.debug("SUCCESS start selenium-server-standalone session for {}:{}".format(ip, port))
            conn.close()
            return response

        # need to read response to keep sending requests
        body = response.read()
        log.info("FAIL {check} start selenium-server-standalone session for {ip}:{port} - {status} : {body}".format(
            check=check,
            ip=ip,
            port=port,
            status=response.status,
            body=body)
        )
        conn.request(method="POST", url=self.path, headers=self.headers, body=self.body)

    response = conn.getresponse()
    conn.close()


def selenium_status(self, ip, port):
    conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))

    parts = self.path.split("/")
    parts[-1] = "status"
    status = "/".join(parts)

    # try to get status for 3 times
    for check in range(3):
        conn.request(method="GET", url=status)
        response = conn.getresponse()
        if response.status == httplib.OK:
            log.debug("SUCCESS get selenium-server-standalone status for {}:{}".format(ip, port))
            log.debug(response.read())
            conn.close()
            return True
        else:
            log.debug("FAIL    get selenium-server-standalone status for {}:{}".format(ip, port))

    conn.close()
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
        return get_desired_capabilities(self)["sessionName"]
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
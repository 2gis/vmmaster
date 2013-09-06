import json
import StringIO
import httplib

from vmmaster.utils import network_utils
from vmmaster.core.config import config
from vmmaster.core.logger import log


class Command(object):
    pass


class StatusException():
    pass


def delete_session(self):
    self.transparent("DELETE")
    clone = self.sessions.get_clone(get_session(self))
    self.clone_factory.utilize_clone(clone)
    return


def create_session(self):
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

    if response.getheader('Content-Length') is None:
        response_body = None
    else:
        content_length = int(response.getheader('Content-Length'))
        response_body = response.read(content_length)

    if response.status != httplib.OK:
        self.clone_factory.utilize_clone(clone)
    else:
        sessionId = json.loads(response_body)["sessionId"]
        self.sessions.add_session(sessionId, clone)

    self.send_reply(response.status, response.getheaders(), response_body)
    return


def session_response(self, ip, port):
    conn = httplib.HTTPConnection("{ip}:{port}".format(ip=ip, port=port))

    # try to get status for 3 times
    for check in range(3):
        conn.request(method="POST", url=self.path, headers=self.headers.dict, body=self.body)
        response = conn.getresponse()
        if response.status == httplib.OK:
            log.debug("SUCCESS start selenium-server-standalone session for {}:{}".format(ip, port))
            conn.close()
            return response

        # need to read response to keep sending requests
        body = response.read()
        log.info("FAIL    start selenium-server-standalone session - {status} : {body}".format(
            status=response.status,
            body=body)
        )

    conn.close()
    return response


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

    new_body = StringIO.StringIO(json.dumps(body))
    self.rfile = new_body
    self.headers.dict["content-length"] = len(self.body)
    return


def get_platform(self):
    body = json.loads(self.body)
    desired_capabilities = body["desiredCapabilities"]
    platform = desired_capabilities["platform"]
    return platform


def get_session(self):
    path = self.path
    parts = path.split("/")
    pos = parts.index("session")
    session = parts[pos + 1]
    return session
# coding: utf-8

import time
import ujson
import logging
from datetime import datetime

from backend import app as backend_app

log = logging.getLogger(__name__)


def getresponse(req, q):
    try:
        q.put(req())
    except Exception as e:
        q.put(e)


def update_log_step(log_step, message=None, control_line=None):
    if message:
        log_step.body = message
    if control_line:
        log_step.control_line = control_line
    log_step.save()


class FakeSession(object):
    user_id = 1
    endpoint_ip = ""
    endpoint_name = ""
    name = ""
    dc = ""
    selenium_session = ""
    take_screenshot = False
    run_script = ""
    created = time.time()
    modified = time.time()
    deleted = ""
    selenium_log = ""

    # State
    status = "waiting"
    reason = ""
    error = ""
    timeouted = False
    closed = False

    # Relationships
    session_steps = []

    def set_user(self, username):
        self.user = username

    def save(self):
        pass

    def add_session_step(self, *args, **kwargs):
        pass

    def __init__(self, name=None, dc=None, id=None):
        if not id:
            self.id = 1
        else:
            self.id = id

        if name:
            self.name = name

        if dc:
            self.dc = ujson.dumps(dc)
            if dc.get("name", None) and not self.name:
                self.name = dc["name"]
            if dc.get("user", None):
                self.set_user(dc["user"])
            if dc.get("takeScreenshot", None):
                self.take_screenshot = True
            if dc.get("runScript", None):
                self.run_script = ujson.dumps(dc["runScript"])
            if dc.get("platform", None):
                self.platform = dc.get('platform')

        if not self.name:
            self.name = "Unnamed session " + str(self.id)


class Session(FakeSession):
    endpoint = None
    current_log_step = None
    vnc_helper = None
    take_screencast = None
    is_active = True

    def __init__(self, name=None, dc=None, id=None):
        super(Session, self).__init__(name, dc, id)
        if dc and dc.get('takeScreencast', None):
            self.take_screencast = True

    @property
    def inactivity(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def duration(self):
        return (datetime.now() - self.created).total_seconds()

    @property
    def info(self):
        stat = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "platform": self.platform,
            "duration": self.duration,
            "inactivity": self.inactivity,
        }

        if self.endpoint_name:
            stat["endpoint"] = {
                "ip": self.endpoint_ip,
                "name": self.endpoint_name
            }
        return stat

    def close(self, reason=None):
        self.closed = True
        if reason:
            self.reason = "%s" % reason
        self.deleted = datetime.now()
        self.save()

        log.info("Session %s closed. %s" % (self.id, self.reason))

    def succeed(self):
        self.status = "succeed"
        self.close()

    def failed(self, tb=None, reason=None):
        if self.closed:
            log.warn("Session %s already closed with reason %s. "
                     "In this method call was tb='%s' and reason='%s'"
                     % (self.id, self.reason, tb, reason))
            return

        self.status = "failed"
        self.error = tb
        self.close(reason)

    def run(self):
        self.modified = datetime.now()
        self.status = "running"
        log.info("Session %s starting on %s (%s)." %
                 (self.id, self.endpoint_name, self.endpoint_ip))

    def timeout(self):
        self.timeouted = True
        self.failed(reason="Session timeout. No activity since %s" % str(self.modified))

    def add_sub_step(self, control_line, body=None):
        if self.current_log_step:
            return self.current_log_step.add_sub_step(control_line, body)

    def add_session_step(self, control_line, body=None, created=None):
        step = super(Session, self).add_session_step(
            control_line=control_line, body=body, created=created
        )
        self.current_log_step = step

        return step

    def make_request(self, port, request):
        status, headers, body = None, None, None

        if request.headers.get("Host"):
            del request.headers['Host']

        url = "http://%s:%s%s" % (self.endpoint_ip, port, request.url)
        parameters = {
            "method": request.method,
            "url": url,
            "headers": request.headers,
            "data": request.data
        }
        parameters = ujson.dumps(parameters)

        for response in backend_app.queue_producer.add_msg_to_queue(
            "vmmaster_session_%s" % self.id,
            parameters
        ):
            if response:
                response = ujson.loads(response)
                status, headers, body = response.status_code, response.headers, response.content
            yield status, headers, body

        yield status, headers, body

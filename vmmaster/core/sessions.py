import time
import json
from Queue import Queue
from threading import Timer, Thread
from traceback import format_exc

import requests
import logging
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

from .db import database
from .config import config
from .logger import log
from .exceptions import SessionException, TimeoutException

from twisted.python.threadable import synchronize


def getresponse(req, q):
    try:
        q.put(req())
    except Exception as e:
        q.put(e)


class RequestHelper(object):
    method = None
    url = None
    headers = None
    body = None

    def __init__(self, method, url="/", headers=None, body=""):
        if headers is None:
            headers = {}
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body

    def __repr__(self):
        return "method:%s url:%s headers:%s body:%s" % (self.method,
                                                        self.url,
                                                        self.headers,
                                                        self.body)


class ShutdownTimer(object):
    def __init__(self, timeout, callback, *args):
        self.__timeout = timeout
        self.__callback = callback
        self.__args = args
        self.__start_time = 0
        self.__timer = Timer(self.__timeout, self.__callback, self.__args)

    def __del__(self):
        self.__timer.cancel()
        del self.__timer

    def start(self):
        self.__timer.start()
        self.__start_time = time.time()

    def restart(self):
        self.__timer.cancel()
        del self.__timer
        self.__timer = Timer(self.__timeout, self.__callback, self.__args)
        self.__timer.start()

    def stop(self):
        self.__timer.cancel()

    def time_elapsed(self):
        return time.time() - self.__start_time


def write_session_log(vmmaster_log_step_id, control_line, body):
    return database.create_session_log_step(
        vmmaster_log_step_id=vmmaster_log_step_id,
        control_line=control_line,
        body=body,
        time=time.time()
    )


class SimpleResponse:
    def __init__(self, status_code=None, headers=None, content=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content


class Session(object):
    id = None
    name = None
    virtual_machine = None
    desired_capabilities = None
    timeouted = False
    closed = False

    vmmaster_log_step = None

    def __init__(self, sessions, name, platform, vm, username=None):
        self.sessions = sessions
        self.name = name
        self.platform = platform
        self.virtual_machine = vm
        self._start = time.time()
        log.info("starting new session on %s." % self.virtual_machine)
        self.db_session = database.create_session(status="running",
                                                  name=self.name,
                                                  time=time.time(),
                                                  username=username)
        self.id = str(self.db_session.id)
        self.timer = ShutdownTimer(config.SESSION_TIMEOUT, self.timeout)
        self.timer.start()
        log.info("session %s started on %s." % (self.id, self.virtual_machine))

    @property
    def user_id(self):
        return self.db_session.user_id

    @property
    def duration(self):
        return time.time() - self._start

    def set_desired_capabilities(self, dc):
        self.desired_capabilities = dc

    def delete(self):
        log.info("deleting session: %s" % self.id)
        if self.virtual_machine:
            if self.virtual_machine.name is not None\
                    and 'preloaded' in self.virtual_machine.name:
                self.virtual_machine.rebuild()
            else:
                self.virtual_machine.delete()

        self.sessions.delete_session(self.id)
        self.timer.stop()
        del self.timer
        log.info("session %s deleted." % self.id)

    def succeed(self):
        self.closed = True
        db_session = database.get_session(self.id)
        db_session.status = "succeed"
        database.update(db_session)
        self.delete()

    def failed(self, tb):
        self.closed = True
        db_session = database.get_session(self.id)
        db_session.status = "failed"
        db_session.error = tb
        database.update(db_session)
        self.delete()

    def close(self):
        self.closed = True
        self.failed("Session closed by user")

    def timeout(self):
        self.timeouted = True
        log.info("TIMEOUT %s session" % self.id)
        try:
            raise TimeoutException("Session timeout")
        except TimeoutException:
            self.failed(format_exc())

    def make_request(self, port, request):
        """ Make http request to some port in session
            and return the response. """

        if request.headers.get("Host"):
            del request.headers['Host']

        if self.vmmaster_log_step:
            write_session_log(
                self.vmmaster_log_step.id,
                "%s %s" % (request.method, request.url),
                request.body)

        self.timer.restart()
        q = Queue()
        url = "http://%s:%s%s" % (self.virtual_machine.ip, port, request.url)

        req = lambda: requests.request(method=request.method,
                                       url=url,
                                       headers=request.headers,
                                       data=request.body)
        t = Thread(target=getresponse, args=(req, q))
        t.daemon = True
        t.start()

        response = None
        while not response:
            if self.timeouted:
                response = SimpleResponse(
                    status_code=500,
                    headers={},
                    content='{"status": 1, "value": "Session timeouted"}'
                )
            elif self.closed:
                response = SimpleResponse(
                    status_code=500,
                    headers={},
                    content='{"status": 1, "value": "Session closed"}'
                )
            elif not t.isAlive():
                response = q.get()
                del q
                del t
                if isinstance(response, Exception):
                    raise response
                response = SimpleResponse(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=response.content
                )
            else:
                t.join(0.1)

        try:
            content_json = json.loads(response.content)
        except ValueError:
            content_json = {}
            log.info("Couldn't parse response content <%s>" %
                     repr(response.content))

        if "screenshot" in content_json.keys():
            content_to_log = ""
        else:
            content_to_log = response.content

        if self.vmmaster_log_step:
            write_session_log(
                self.vmmaster_log_step.id,
                "%s" % response.status_code,
                content_to_log)

        return response.status_code, response.headers, response.content

    @property
    def info(self):
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "duration": self.duration,
            "vm_name": self.virtual_machine.name,
        }


class Sessions(object):
    synchronized = ['get_session', 'delete_session']

    def __init__(self):
        self.map = {}

    def __iter__(self):
        return iter(self.map.items())

    def delete(self):
        session_ids = [session_id for session_id in self.map]
        for session_id in session_ids:
            session = self.get_session(session_id)
            session.delete()

    def start_session(self, session_name, platform, vm, username=None):
        session = Session(self, session_name, platform, vm, username)
        self.map[str(session.id)] = session
        return session

    def get_session(self, session_id):
        try:
            return self.map[str(session_id)]
        except KeyError:
            raise SessionException("There is no active session %s" % session_id)

    def delete_session(self, session_id):
        del self.map[str(session_id)]

synchronize(Sessions)
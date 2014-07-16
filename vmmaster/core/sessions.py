import time
import httplib
from threading import Timer

from .db import database
from .config import config
from .logger import log


class RequestHelper(object):
    method = None
    url = None
    headers = None
    body = None

    def __init__(self, method, url="/", headers={}, body=""):
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body


class ShutdownTimer(object):
    def __init__(self, timeout, callback, *args):
        self.__timeout = timeout
        self.__callback = callback
        self.__args = args
        self.__start_time = 0
        self.__timer = Timer(self.__timeout, self.__callback, self.__args)

    def __del__(self):
        log.debug("ShutdownTimer __del__")
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


class Session(object):
    id = None
    name = None
    virtual_machine = None
    timeouted = False

    def __init__(self, sessions, name=None):
        self.sessions = sessions
        self.name = name
        log.info("starting new session.")
        db_session = database.createSession(status="running", name=self.name, time=time.time())
        self.id = db_session.id
        self.timer = ShutdownTimer(config.SESSION_TIMEOUT, self.timeout)
        self.timer.start()
        log.info("session %s started." % self.id)

    def delete(self):
        log.debug("deleting session: %s" % self.id)
        if self.virtual_machine:
            self.virtual_machine.delete()
            self.virtual_machine = None

        self.sessions.delete_session(self.id)
        self.timer.stop()
        del self.timer
        log.debug("session %s deleted." % self.id)

    def succeed(self):
        db_session = database.getSession(self.id)
        db_session.status = "succeed"
        database.update(db_session)
        self.delete()

    def failed(self, tb):
        db_session = database.getSession(self.id)
        db_session.status = "failed"
        db_session.error = tb
        database.update(db_session)
        self.delete()

    def timeout(self):
        self.timeouted = True

    def make_request(self, port, request):
        """ Make request to selenium-server-standalone
            and return the response. """
        conn = httplib.HTTPConnection("{ip}:{port}".format(ip=self.virtual_machine.ip, port=port))
        conn.request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            body=request.body
        )

        self.timer.restart()

        response = conn.getresponse()

        if response.getheader('Content-Length') is None:
            response_body = None
        else:
            content_length = int(response.getheader('Content-Length'))
            response_body = response.read(content_length)

        conn.close()

        return response.status, dict(x for x in response.getheaders()), response_body


class Sessions(object):
    def __init__(self):
        # dispatcher.connect(self.__delete_session, signal=Signals.DELETE_SESSION, sender=dispatcher.Any)
        self.map = {}

    def __del__(self):
        pass
        # dispatcher.disconnect(self.__delete_session, signal=Signals.DELETE_SESSION, sender=dispatcher.Any)

    def delete(self):
        session_ids = [session_id for session_id in self.map]
        for session_id in session_ids:
            session = self.get_session(session_id)
            session.delete()

    def start_session(self, session_name):
        session = Session(self, session_name)
        self.map[str(session.id)] = session
        return session

    def get_session(self, session_id):
        return self.map[session_id]

    def delete_session(self, session_id):
        del self.map[str(session_id)]
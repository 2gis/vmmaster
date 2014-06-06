import time
import sys
from threading import Timer

from .dispatcher import dispatcher, Signals
from .db import database
from .config import config
from .logger import log


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
    timeouted = False

    def __init__(self, name=None):
        db_session = database.createSession(status="running", name=name, time=time.time())
        self.id = db_session.id
        self.timer = ShutdownTimer(config.SESSION_TIMEOUT, self.timeout)
        self.timer.start()

    def delete(self):
        if hasattr(self, "clone"):
            dispatcher.send(signal=Signals.DELETE_CLONE, sender=self, clone=self.clone)

        dispatcher.send(signal=Signals.DELETE_SESSION, sender=self, session_id=str(self.id))

        self.timer.stop()
        del self.timer

    def succeed(self):
        db_session = database.getSession(self.id)
        db_session.status = "succeed"
        database.update(db_session)
        self.delete()
        del self

    def failed(self, tb):
        db_session = database.getSession(self.id)
        db_session.status = "failed"
        db_session.error = tb
        database.update(db_session)
        self.delete()
        del self

    def timeout(self):
        # dispatcher.send(signal=Signals.DELETE_CLONE, sender=self, clone=self.clone, timeouted=True)
        self.timeouted = True


class Sessions(object):
    def __init__(self):
        dispatcher.connect(self.__delete_session, signal=Signals.DELETE_SESSION, sender=dispatcher.Any)
        self.map = {}

    def delete(self):
        session_ids = [session_id for session_id in self.map]
        for session_id in session_ids:
            session = self.get_session(session_id)
            del session

    def start_session(self, session_name):
        session = Session(session_name)
        self.map[str(session.id)] = session
        return session

    def get_session(self, session_id):
        return self.map[session_id]

    def __delete_session(self, session_id):
        del self.map[session_id]
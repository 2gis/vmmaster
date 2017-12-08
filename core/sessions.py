# coding: utf-8

import time
import logging

from collections import OrderedDict
from threading import Thread, Lock

from core.config import config
from core.exceptions import SessionException

log = logging.getLogger(__name__)


def update_log_step(log_step, message=None, control_line=None):
    if message:
        log_step.body = message
    if control_line:
        log_step.control_line = control_line
    log_step.save()


class SimpleResponse:
    def __init__(self, status_code=None, headers=None, content=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content


class SessionWorker(Thread):
    def __init__(self, sessions, context):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.sessions = sessions
        self.context = context

    def run(self):
        while self.running:
            with self.context():
                for session in self.sessions.running():
                    if not session.is_active and session.inactivity > config.SESSION_TIMEOUT:
                        session.timeout()
                time.sleep(1)

    def stop(self):
        self.running = False
        self.join(1)
        log.info("SessionWorker stopped")


class SessionCache:
    def __init__(self, max_size=100):
        self._max_size = max_size
        self._cache = OrderedDict()
        self._cache_lock = Lock()

    def to_json(self):
        return self._cache.keys()

    def __getitem__(self, item):
        return self._cache[item]

    def __setitem__(self, key, value):
        with self._cache_lock:
            self._check_limit()
            self._cache[key] = value

    def _check_limit(self):
        if len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

    def clear(self):
        with self._cache_lock:
            self._cache.clear()


class Sessions(object):
    _worker = None
    _cache = None

    def __init__(self, database, context, session_worker_class=SessionWorker, cache_class=SessionCache):
        self.db = database
        self.context = context

        if session_worker_class:
            self._worker = session_worker_class(self, self.context)

        if cache_class:
            self._cache = cache_class()

    def start_workers(self):
        if self._worker:
            self._worker.start()

    def stop_workers(self):
        if self._worker:
            self._worker.stop()

    def active(self, provider_id=None):
        return self.db.get_active_sessions(provider_id=provider_id)

    def running(self):
        return [s for s in self.active() if s.status == "running"]

    def waiting(self):
        return [s for s in self.active() if s.status == "waiting"]

    def kill_all(self):
        for session in self.active():
            session.failed()

    def get_session(self, session_id, maybe_closed=False):
        """
        :param session_id: integer
        :param maybe_closed: boolean
        :return: Session
        """
        try:
            session = self._cache[session_id]
        except (KeyError, TypeError):
            log.debug('Cache miss (item={})'.format(session_id))
            session = self.db.get_session(session_id)

        if not session:
            raise SessionException("There is no active session {} (Unknown session)".format(session_id))

        if session.closed and not maybe_closed:
            raise SessionException("Session {}({}) already closed earlier".format(session_id, session.reason))

        log.debug("Recovering {} from db".format(session))
        with self.context():
            session.restore()

        if self._cache:
            self._cache[session_id] = session

        return session

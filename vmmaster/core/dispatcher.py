from pydispatch import dispatcher


class Signals(object):
    DELETE_CLONE = "delete_clone"
    SESSION_TIMEOUT = "session_timeout"
    DELETE_SESSION = "delete_session"
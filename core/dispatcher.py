from pydispatch import dispatcher


class Signals(object):
    DELETE_VIRTUAL_MACHINE = "delete_virtual_machine"
    SESSION_TIMEOUT = "session_timeout"
    DELETE_SESSION = "delete_session"
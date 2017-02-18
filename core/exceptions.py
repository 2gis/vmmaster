# coding: utf-8


class PlatformException(Exception):
    pass


class SessionException(Exception):
    pass


class ClonesException(Exception):
    pass


class NoMacError(Exception):
    pass


class CreationException(Exception):
    pass


class TimeoutException(Exception):
    pass


class ConnectionError(Exception):
    pass


class NoSuchEndpoint(Exception):
    pass


class QueueItemNotFound(Exception):
    pass
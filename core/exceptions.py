# coding: utf-8


class PlatformException(Exception):
    pass


class SessionException(Exception):
    pass


class CreationException(Exception):
    pass


class RequestTimeoutException(Exception):
    pass


class RequestException(Exception):
    pass


class TimeoutException(Exception):
    pass


class ConnectionError(Exception):
    pass


class EndpointUnreachableError(Exception):
    pass

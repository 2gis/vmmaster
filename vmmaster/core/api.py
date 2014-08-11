from flask import request


class ApiHandler(object):
    _headers = None
    _body = None

    _reply_code = None
    _reply_headers = None
    _reply_body = None

    _log_step = None
    _session_id = None

    def __init__(self, platforms, sessions):
        self.platforms = platforms
        self.sessions = sessions

    def __call__(self, path):
        self.method = request.method
        self.path = request.path
        self.clientproto = request.headers.environ['SERVER_PROTOCOL']
        self.headers = dict(request.headers.items())
        self.body = request.data
        return self.requestReceived(self.method, self.path, self.clientproto)
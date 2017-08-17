# coding: utf-8

from flask.ext.httpauth import HTTPBasicAuth
from functools import wraps
from flask import request, make_response, current_app
from json import loads, dumps
from werkzeug.datastructures import Authorization

anonymous = Authorization('basic', {'username': 'anonymous', 'password': None})


def user_exists(token):
    return current_app.database.get_user(token=token)


def user_not_found():
    error_msg = {
        "status": 1,
        "value": "User not found in service",
        "message": "Please register in service"
    }
    res = make_response(dumps(error_msg))
    res.status_code = 401
    return res


def authentificate_failed():
    error_msg = {
        "status": 1,
        "value": "Authentification was failed",
        "message": "Please try again"
    }
    res = make_response(dumps(error_msg))
    res.status_code = 401
    return res


class DesiredCapabilitiesAuth(HTTPBasicAuth):
    def get_token_from_caps(self):
        try:
            body = loads(request.data)
        except ValueError:
            return None
        try:
            caps = body['desiredCapabilities']
        except KeyError:
            return None

        return caps.get("token", None)

    def _restore_username(self):
        body = loads(request.data)
        desired_capabilities = body["desiredCapabilities"]

        username = current_app.database.get_user(token=desired_capabilities["token"]).username
        desired_capabilities["user"] = username
        body["desiredCapabilities"] = desired_capabilities

        request.data = dumps(body)

    def login_required(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            _token = self.get_token_from_caps()
            if _token:
                if not user_exists(_token):
                    return user_not_found()
                self._restore_username()
            return f(*args, **kwargs)
        return decorated

auth = DesiredCapabilitiesAuth()

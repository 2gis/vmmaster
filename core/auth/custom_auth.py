# -*- coding: utf-8 -*-
from flask.ext.httpauth import HTTPBasicAuth
from functools import wraps
from flask import request, make_response
from json import loads, dumps
from werkzeug.datastructures import Authorization
import core.db as db

anonymous = Authorization('basic', {'username': 'anonymous', 'password': None})


def user_exists(username):
    return db.database.get_user(username=username)


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

    def get_auth_from_caps(self):
        req = request.proxy.request
        try:
            body = loads(req.body)
        except ValueError:
            return anonymous
        try:
            caps = body['desiredCapabilities']
        except KeyError:
            return anonymous
        user = caps.get("user", None)
        if user is None:
            return anonymous
        token = caps.get("token", None)
        return Authorization('basic', {"username": user, "password": token})

    @property
    def username(self):
        return self.get_auth_from_caps().username

    def login_required(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            _auth = self.get_auth_from_caps()
            if not user_exists(_auth.username):
                return user_not_found()
            token = self.get_password_callback(_auth.username)
            if not self.authenticate(_auth, token):
                return authentificate_failed()
            return f(*args, **kwargs)
        return decorated

auth = DesiredCapabilitiesAuth()

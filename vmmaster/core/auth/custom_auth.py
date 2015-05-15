# -*- coding: utf-8 -*-
from flask.ext.httpauth import HTTPBasicAuth
from functools import wraps
from flask import request
from json import loads as json_loads
from werkzeug.datastructures import Authorization
import vmmaster.core.db as db

anonymous = Authorization('basic', {'username': 'anonymous', 'password': None})


def user_exists(username):
    return db.database.get_user(username=username)


class DesiredCapabilitiesAuth(HTTPBasicAuth):

    def get_auth_from_caps(self):
        req = request.proxy.request
        try:
            body = json_loads(req.body)
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
                return self.auth_error_callback()
            token = self.get_password_callback(_auth.username)
            if not self.authenticate(_auth, token):
                return self.auth_error_callback()
            return f(*args, **kwargs)
        return decorated

auth = DesiredCapabilitiesAuth()
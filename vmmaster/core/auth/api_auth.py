# -*- coding: utf-8 -*-

from flask.ext.httpauth import HTTPBasicAuth
from functools import wraps
from flask import request, make_response
import vmmaster.core.db as db


def account_is_locked():
    res = make_response("Account is locked")
    res.status_code = 403
    return res


def access_denied():
    res = make_response("Access denied")
    res.status_code = 403
    return res


class APIBasicAuth(HTTPBasicAuth):
    def login_required(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            # We need to ignore authentication headers for OPTIONS to avoid
            # unwanted interactions with CORS.
            # Chrome and Firefox issue a preflight OPTIONS request to check
            # Access-Control-* headers, and will fail if it returns 401.
            if request.method != 'OPTIONS':
                if auth:
                    # Check user is active
                    client = db.database.get_user(username=auth.username)
                    if not client.is_active:
                        return account_is_locked()
                    # Check user access rights for resource
                    resource_id = kwargs['user_id']
                    if client.id != resource_id:
                        return access_denied()
                    password = self.get_password_callback(auth.username)
                else:
                    password = None
                if not self.authenticate(auth, password):
                    return self.auth_error_callback()
            return f(*args, **kwargs)
        return decorated

auth = APIBasicAuth()


@auth.hash_password
def get_password(username):
    user = db.database.get_user(username=username)
    if user:
        return user.password
    else:
        return None
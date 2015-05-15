# coding: utf-8

import unittest
import json
from mock import Mock, PropertyMock, patch
from base64 import urlsafe_b64encode

from vmmaster.webdriver import log_request
from vmmaster.core.auth.custom_auth import anonymous
from vmmaster.core.auth.custom_auth import auth as wd_auth
from vmmaster.core.auth.api_auth import auth as api_auth


def get_user(username):
    if username == anonymous.username:
        user = Mock(__name__="User")
        user.is_active = PropertyMock(return_value=True)
        user.id = 1
        return user
    else:
        return False

from vmmaster.core import db
db.database = Mock()
db.database.get_user = get_user


def decorate_this(*args, **kwargs):
    """
    Mock function for login_required decorator testing
    """
    pass


class TestWDAuthPositive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        cls.app = Flask(__name__)
        from vmmaster.core.config import setup_config
        setup_config('data/config.py')
        from vmmaster.core.platforms import Platforms
        cls.platform = Platforms().platforms.keys()[0]

    def setUp(self):
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def push_to_ctx(self):
        """
        Push current request data to request context
        """
        request_data = json.dumps(self.desired_caps)
        self.ctx = self.app.test_request_context(method="POST",
                                                 data=request_data)
        self.ctx.push()
        log_request()

    def set_auth_credentials(self, username=None, token=None):
        self.desired_caps["desiredCapabilities"]["user"] = username
        if token:
            self.desired_caps["desiredCapabilities"]["token"] = token

    def test_auth_without_credentials(self):
        self.push_to_ctx()
        wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_existing(self):
        self.set_auth_credentials(username=anonymous.username,
                                  token=anonymous.password)
        self.push_to_ctx()
        wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_not_existing_user(self):
        self.set_auth_credentials(username="not_existing_user")
        # Token doesn't matter
        self.push_to_ctx()
        resp = wd_auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())

    def test_auth_wrong_token(self):
        existing_user = anonymous.username
        wrong_token = "not" + str(anonymous.password)
        self.set_auth_credentials(username=existing_user, token=wrong_token)
        self.push_to_ctx()
        resp = wd_auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())


@api_auth.verify_password
def always_verify(*args, **kwargs):
    return True


class TestAPIAuthPositive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        cls.app = Flask(__name__)
        from vmmaster.core.config import setup_config
        setup_config('data/config.py')
        from vmmaster.core.platforms import Platforms
        cls.platform = Platforms().platforms.keys()[0]

        cls.method = "GET"
        cls.headers = dict(Authorization="Basic " + urlsafe_b64encode(
            str(anonymous.username) + ":" + str(anonymous.password))
        )

    def push_to_ctx(self):
        """
        Push current request data to request context
        """
        self.ctx = self.app.test_request_context(method=self.method,
                                                 headers=self.headers)
        self.ctx.push()

    def test_access_to_allowed_resource(self):
        self.push_to_ctx()
        # GET api/user/1 (his own id)
        resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNone(resp)

    def test_access_to_forbidden_resource(self):
        self.push_to_ctx()
        # GET api/user/2 (forbidden resource)
        resp = api_auth.login_required(decorate_this)(user_id=2)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data, "Access denied")

    def test_access_by_locked_user(self):
        with patch.object(db.database, "get_user"):
            locked_user = Mock()
            locked_user.is_active = False
            db.database.get_user = Mock(return_value=locked_user)
            self.push_to_ctx()
            resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data, "Account is locked")

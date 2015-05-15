# coding: utf-8
import unittest
import json
from mock import Mock

from vmmaster.webdriver import log_request
from vmmaster.core.auth.custom_auth import auth, anonymous


def get_user(username):
    if username == anonymous.username:
        return True
    else:
        return False

from vmmaster.core import db
db.database = Mock()
db.database.get_user = get_user


def decorate_this():
    """
    Mock function for login_required decorator testing
    """
    pass


class TestCustomAuthPositive(unittest.TestCase):
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
        auth.login_required(decorate_this)()
        self.assertEqual(auth.username, anonymous.username)

    def test_auth_existing(self):
        self.set_auth_credentials(username=anonymous.username,
                                  token=anonymous.password)
        self.push_to_ctx()
        auth.login_required(decorate_this)()
        self.assertEqual(auth.username, anonymous.username)

    def test_auth_not_existing_user(self):
        self.set_auth_credentials(username="not_existing_user")
        # Token doesn't matter
        self.push_to_ctx()
        resp = auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())

    def test_auth_wrong_token(self):
        existing_user = anonymous.username
        wrong_token = "not" + str(anonymous.password)
        self.set_auth_credentials(username=existing_user, token=wrong_token)
        self.push_to_ctx()
        resp = auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())

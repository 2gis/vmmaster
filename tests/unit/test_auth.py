# coding: utf-8

import json

from mock import Mock, patch
from helpers import BaseTestCase


def decorate_this(*args, **kwargs):
    """
    Mock function for login_required decorator testing
    """
    pass


class TestWDAuthPositive(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        cls.app = Flask(__name__)
        cls.app.running = True

        from vmmaster.core.config import setup_config
        setup_config('data/config.py')

        with patch('vmmaster.core.network.network.Network', Mock()), \
                patch('vmmaster.core.connection.Virsh', Mock()):
            from vmpool.platforms import Platforms
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
        from vmmaster.webdriver import log_request
        log_request()

    def set_auth_credentials(self, username=None, token=None):
        self.desired_caps["desiredCapabilities"]["user"] = username
        if token:
            self.desired_caps["desiredCapabilities"]["token"] = token

    def test_auth_without_credentials(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.custom_auth import auth as wd_auth
            from vmmaster.core.auth.custom_auth import anonymous
            self.push_to_ctx()
            wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_existing(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.custom_auth import auth as wd_auth
            from vmmaster.core.auth.custom_auth import anonymous
            self.set_auth_credentials(username=anonymous.username,
                                      token=anonymous.password)
            self.push_to_ctx()
            wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_not_existing_user(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.custom_auth import auth as wd_auth
            self.set_auth_credentials(username="not_existing_user")
            # Token doesn't matter
            self.push_to_ctx()
            resp = wd_auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())

    def test_auth_wrong_token(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.custom_auth import auth as wd_auth
            from vmmaster.core.auth.custom_auth import anonymous
            existing_user = anonymous.username
            wrong_token = "not" + str(anonymous.password)
            self.set_auth_credentials(username=existing_user,
                                      token=wrong_token)
            self.push_to_ctx()
            resp = wd_auth.login_required(decorate_this)()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers.keys())


class TestAPIAuthPositive(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        cls.app = Flask(__name__)

        from vmmaster.core.config import setup_config
        setup_config('data/config.py')

        with patch('vmmaster.core.network.network.Network', Mock()), \
                patch('vmmaster.core.connection.Virsh', Mock()):
            from vmpool.platforms import Platforms
            cls.platform = Platforms().platforms.keys()[0]

        cls.method = "GET"
        from base64 import urlsafe_b64encode
        from vmmaster.core.auth.custom_auth import anonymous
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
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.api_auth import auth as api_auth

            @api_auth.verify_password
            def always_verify(*args, **kwargs):
                return True

            self.push_to_ctx()
            # GET api/user/1 (his own id)
            resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNone(resp)

    def test_access_to_forbidden_resource(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))):
            from vmmaster.core.auth.api_auth import auth as api_auth

            @api_auth.verify_password
            def always_verify(*args, **kwargs):
                return True

            self.push_to_ctx()
            # GET api/user/2 (forbidden resource)
            resp = api_auth.login_required(decorate_this)(user_id=2)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data, "Access denied")

    def test_access_by_locked_user(self):
        from vmmaster.core import db
        with patch.object(db, "database", new=Mock(
                get_user=Mock(return_value=Mock(is_active=False)))):
            from vmmaster.core.auth.api_auth import auth as api_auth

            @api_auth.verify_password
            def always_verify(*args, **kwargs):
                return True

            self.push_to_ctx()
            resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data, "Account is locked")

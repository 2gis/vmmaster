# coding: utf-8

import json

from mock import Mock, patch
from helpers import BaseTestCase
from flask import Flask


def decorate_this(*args, **kwargs):
    """
    Mock function for login_required decorator testing
    """
    pass


class TestWDAuthPositive(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.running = True
        cls.app.database = None

        from core.config import setup_config
        setup_config('data/config.py')

        with patch('core.network.Network', Mock()), \
                patch('core.connection.Virsh', Mock()):
            from vmpool.platforms import Platforms
            cls.platform = Platforms().platforms.keys()[0]

    def setUp(self):
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def tearDown(self):
        self.ctx.pop()

    def push_to_ctx(self):
        """
        Push current request data to request context
        """
        request_data = json.dumps(self.desired_caps)
        self.ctx = self.app.test_request_context(method="POST",
                                                 data=request_data)
        self.ctx.push()

    def set_auth_credentials(self, username=None, token=None):
        self.desired_caps["desiredCapabilities"]["user"] = username
        if token:
            self.desired_caps["desiredCapabilities"]["token"] = token

    def test_auth_without_credentials(self):
        from core.auth.custom_auth import auth as wd_auth
        from core.auth.custom_auth import anonymous
        self.push_to_ctx()
        with patch(
            "flask.current_app.database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))
        ):
            wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_existing(self):
        from core.auth.custom_auth import auth as wd_auth
        from core.auth.custom_auth import anonymous
        self.set_auth_credentials(username=anonymous.username,
                                  token=anonymous.password)
        self.push_to_ctx()
        with patch(
            "flask.current_app.database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))
        ):
            wd_auth.login_required(decorate_this)()
        self.assertEqual(wd_auth.username, anonymous.username)

    def test_auth_not_existing_user(self):
        from core.auth.custom_auth import auth as wd_auth
        self.set_auth_credentials(username="not_existing_user")
        # Token doesn't matter
        self.push_to_ctx()

        with patch(
            "flask.current_app.database", new=Mock(
                get_user=Mock(return_value=None))
        ):
            resp = wd_auth.login_required(decorate_this)()

        success_data = {
            "status": 1,
            "value": "User not found in service",
            "message": "Please register in service"
        }
        self.assertEqual(resp.status_code, 401)
        self.assertDictEqual(json.loads(resp.data), success_data)

    def test_auth_wrong_token(self):
        from core.auth.custom_auth import auth as wd_auth
        from core.auth.custom_auth import anonymous
        existing_user = anonymous.username
        wrong_token = "not" + str(anonymous.password)
        self.set_auth_credentials(username=existing_user,
                                  token=wrong_token)
        self.push_to_ctx()

        with patch(
            "flask.current_app.database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))
        ):
            resp = wd_auth.login_required(decorate_this)()

        success_data = {
            "status": 1,
            "value": "Authentification was failed",
            "message": "Please try again"
        }
        self.assertEqual(resp.status_code, 401)
        self.assertDictEqual(json.loads(resp.data), success_data)


class TestAPIAuthPositive(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.database = None

        from core.config import setup_config
        setup_config('data/config.py')

        with patch('core.network.Network', Mock()), \
                patch('core.connection.Virsh', Mock()):
            from vmpool.platforms import Platforms
            cls.platform = Platforms().platforms.keys()[0]

        cls.method = "GET"
        from base64 import urlsafe_b64encode
        from core.auth.custom_auth import anonymous
        cls.headers = dict(Authorization="Basic " + urlsafe_b64encode(
            str(anonymous.username) + ":" + str(anonymous.password))
        )

    def tearDown(self):
        self.ctx.pop()

    def push_to_ctx(self):
        """
        Push current request data to request context
        """
        self.ctx = self.app.test_request_context(method=self.method,
                                                 headers=self.headers)
        self.ctx.push()

    def test_access_to_allowed_resource(self):
        from core.auth.api_auth import auth as api_auth

        @api_auth.verify_password
        def always_verify(*args, **kwargs):
            return True

        self.push_to_ctx()

        with patch(
            "flask.current_app.database",
            new=Mock(get_user=Mock(return_value=Mock(id=1, is_active=True)))
        ):
            # GET api/user/1 (his own id)
            resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNone(resp)

    def test_access_to_forbidden_resource(self):
        from core.auth.api_auth import auth as api_auth

        @api_auth.verify_password
        def always_verify(*args, **kwargs):
            return True

        self.push_to_ctx()
        with patch("flask.current_app.database", new=Mock(
                get_user=Mock(return_value=Mock(id=1, is_active=True)))
        ):
            # GET api/user/2 (forbidden resource)
            resp = api_auth.login_required(decorate_this)(user_id=2)
        self.assertIsNotNone(resp)

        success_data = {
            "status": 1,
            "value": "Access denied",
            "message": "Please contact your administrator of service"
        }
        self.assertEqual(resp.status_code, 403)
        self.assertDictEqual(json.loads(resp.data), success_data)

    def test_access_by_locked_user(self):
        from core.auth.api_auth import auth as api_auth

        @api_auth.verify_password
        def always_verify(*args, **kwargs):
            return True

        self.push_to_ctx()
        with patch("flask.current_app.database", new=Mock(
            get_user=Mock(return_value=Mock(is_active=False)))
        ):
            resp = api_auth.login_required(decorate_this)(user_id=1)
        self.assertIsNotNone(resp)

        success_data = {
            "status": 1,
            "value": "Account is locked",
            "message": "Please contact your administrator of service"
        }
        self.assertEqual(resp.status_code, 403)
        self.assertDictEqual(json.loads(resp.data), success_data)

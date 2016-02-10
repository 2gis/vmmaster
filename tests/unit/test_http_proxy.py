# coding: utf-8

from mock import Mock, patch
from core.config import setup_config

from helpers import (vmmaster_server_mock, server_is_up, server_is_down,
                     BaseTestCase, get_free_port, ServerMock)

import requests


class TestHttpProxy(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.host = "localhost"
        self.port = 9001
        self.address = (self.host, self.port)
        self.vmmaster = vmmaster_server_mock(self.port)
        server_is_up(self.address)
        self.free_port = get_free_port()

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

        from core.sessions import Session
        self.session = Session()
        self.session.endpoint_ip = "localhost"

    def tearDown(self):
        self.session.delete()
        self.ctx.pop()
        self.vmmaster.app.sessions.kill_all()
        self.vmmaster.stop_services()
        server_is_down(self.address)

    def test_proxy_successful(self):
        server = ServerMock(self.host, self.free_port)
        server.start()
        with patch(
            'core.sessions.Sessions.get_session', Mock(
                return_value=self.session)
        ):
            response = requests.get(
                "http://%s:%s/proxy/session/%s/port/%s/" %
                (self.host, self.port, self.session.id, self.free_port)
            )
        server.stop()
        self.assertEqual("ok", response.content)

    def test_proxy_responses_when_trying_to_connect_failed(self):
        with patch(
            'core.sessions.Sessions.get_session', Mock(
                return_value=self.session)
        ):
            response = requests.get(
                "http://%s:%s/proxy/session/%s/port/%s/" %
                (self.host, self.port, self.session.id, self.free_port)
            )
        self.assertEqual(
            "Request forwarding failed:\n"
            "Connection was refused by other side: 111: Connection refused.",
            response.content)

    def test_proxy_to_session_that_doesnt_exist(self):
        self.session.succeed()
        with patch(
            'flask.current_app.database.get_session',
            Mock(return_value=self.session)
        ):
            response = requests.get(
                "http://%s:%s/proxy/session/%s/port/%s/" %
                (self.host, self.port, self.session.id, self.free_port)
            )
        self.assertEqual(
            "There is no active session %s" % self.session.id,
            response.content
        )

    def test_proxy_with_wrong_path(self):
        response = requests.get(
            "http://%s:%s/proxy/asdf/%s/" %
            (self.host, self.port, self.free_port)
        )
        self.assertEqual(
            "Couldn't parse request uri, "
            "make sure you request uri has "
            "/proxy/session/<session_id>/port/<port_number>/<destination>",
            response.content)

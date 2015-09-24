# coding: utf-8

from mock import Mock, patch
from core.config import setup_config

from helpers import (vmmaster_server_mock, server_is_up, server_is_down,
                     BaseTestCase, get_free_port, ServerMock)

import requests


class TestHttpProxy(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmmaster = vmmaster_server_mock(self.address[1])
        server_is_up(self.address)
        self.free_port = get_free_port()
        self.connection_props = self.address + (self.free_port,)

        self.ctx = self.vmmaster.app.app_context()
        self.ctx.push()

        from core.sessions import Session
        self.session = Session()
        self.session.endpoint_ip = "localhost"

    def tearDown(self):
        self.session.delete()
        self.ctx.pop()
        with patch('core.db.database', Mock()):
            del self.vmmaster
            server_is_down(self.address)

    def test_proxy_successful(self):
        server = ServerMock(self.address[0], self.free_port)
        server.start()
        with patch(
            'core.sessions.Sessions.get_session', Mock(
                return_value=self.session)
        ):
            response = requests.get(
                "http://%s:%s/proxy/session/1/port/%s/" % self.connection_props
            )
        server.stop()
        self.assertEqual("ok", response.content)

    def test_proxy_responses_when_trying_to_connect_failed(self):
        with patch(
            'core.sessions.Sessions.get_session', Mock(
                return_value=self.session)
        ):
            response = requests.get(
                "http://%s:%s/proxy/session/1/port/%s/" % self.connection_props
            )
        self.assertEqual(
            "Request forwarding failed:\n"
            "Connection was refused by other side: 111: Connection refused.",
            response.content)

    def test_proxy_to_session_that_doesnt_exist(self):
        response = requests.get(
            "http://%s:%s/proxy/session/1/port/%s/" % self.connection_props
        )
        self.assertEqual("There is no active session 1", response.content)

    def test_proxy_with_wrong_path(self):
        response = requests.get(
            "http://%s:%s/proxy/asdf/%s/" % self.connection_props
        )
        self.assertEqual(
            "Couldn't parse request uri, "
            "make sure you request uri has "
            "/proxy/session/<session_id>/port/<port_number>/<destination>",
            response.content)

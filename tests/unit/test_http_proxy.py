from mock import Mock, patch
from core.config import setup_config

from helpers import (vmmaster_server_mock, server_is_up, server_is_down,
                     BaseTestCase, get_free_port, ServerMock)

import requests


@patch('core.db.database', new=Mock())
class TestHttpProxy(BaseTestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9001)
        self.vmmaster = vmmaster_server_mock(self.address[1])
        server_is_up(self.address)
        self.free_port = get_free_port()
        self.connection_props = self.address + (self.free_port,)

        with patch('core.db.database', Mock()):
            from core.sessions import Session
            self.session = Session()
            self.session.id = 1
            self.session.endpoint_ip = "localhost"

    def tearDown(self):
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

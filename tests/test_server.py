import unittest
import json
import httplib

from mock import Mock
from nose.twistedtools import reactor
from human_curl import request

from vmmaster.core.config import setup_config

# Mocking
from vmmaster.core import db
db.database = Mock()
from vmmaster.core import connection
connection.Virsh = Mock()
from vmmaster.core.network import network
network.Network = Mock()
from vmmaster.core.platform_server import RequestHandler
RequestHandler.take_screenshot = Mock()
from vmmaster.core.virtual_machine.clone import Clone
Clone.clone_origin = Mock()
Clone.define_clone = Mock()
Clone.start_virtual_machine = Mock()
Clone.drive_path = Mock()
from vmmaster.core import commands
commands.check_vm_online = Mock()
commands.start_selenium_session = Mock(return_value=(200, {}, json.dumps({'sessionId': "1"})))
from vmmaster.core.utils import utils
utils.delete_file = Mock()

from vmmaster.server import VMMasterServer
from vmmaster.core.utils.network_utils import get_socket


def new_session_request(address, desired_caps):
    request('POST', "http://%s:%s/wd/hub/session" % address, data=json.dumps(desired_caps))


def server_is_up(address):
    import time
    s = get_socket(address[0], address[1])
    time_start = time.time()
    timeout = 5
    while not s:
        s = get_socket(address[0], address[1])
        time.sleep(0.1)
        if time.time() - time_start > timeout:
            raise RuntimeError("server is not running on %s:%s" % address)


class TestServer(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.server.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)

    def tearDown(self):
        del self.server

    def test_server_create_new_session_ok(self):
        new_session_request(self.address, self.desired_caps)
        vm_count = self.server.platforms.vm_count
        self.assertEqual(1, vm_count)

    def test_server_delete_timeouted_session(self):
        from vmmaster.core.sessions import Session
        Session.timeouted = True

        self.assertEqual(0, self.server.platforms.vm_count)

        new_session_request(self.address, self.desired_caps)
        vm_count = self.server.platforms.vm_count

        self.assertEqual(0, vm_count)


class TestServerShutdown(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.server.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)

    def test_server_shutdown(self):
        del self.server

    def test_server_shutdown_delete_sessions(self):
        from vmmaster.core.sessions import Session
        Session.timeouted = False
        new_session_request(self.address, self.desired_caps)

        sessions = self.server.sessions.map
        self.assertEqual(1, len(sessions))

        del self.server
        self.assertEqual(0, len(sessions))

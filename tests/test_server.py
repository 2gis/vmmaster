import unittest
import json
import time
from uuid import uuid4

from mock import Mock
from nose.twistedtools import reactor

from vmmaster.core.config import setup_config

# Mocking
from vmmaster.core import db
db.database = Mock()
from vmmaster.core import connection
connection.Virsh.__new__ = Mock()
from vmmaster.core.network import network
network.Network.__new__ = Mock()
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
from vmmaster.core.sessions import Session


def request(host, method, url, headers={}, body=None):
    import httplib
    conn = httplib.HTTPConnection(host)
    conn.request(method=method, url=url, headers=headers, body=body)
    response = conn.getresponse()
    class Response(object): pass
    r = Response()
    r.status = response.status
    r.headers = response.getheaders()
    r.content = response.read()
    conn.close()
    return r


def new_session_request(address, desired_caps):
    return request("%s:%s" % address, "POST", "/wd/hub/session", body=json.dumps(desired_caps))


def delete_session_request(address, session):
    return request("%s:%s" % address, "DELETE", "/wd/hub/session/%s" % str(session))


def get_session_request(address, session):
    return request("%s:%s" % address, "GET", "/wd/hub/session/%s" % str(session))


def server_is_up(address):
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
        Session.timeouted = False
        del self.server

    def test_server_create_new_session(self):
        new_session_request(self.address, self.desired_caps)
        vm_count = self.server.platforms.vm_count
        self.assertEqual(1, vm_count)

    def test_server_maximum_vm_running(self):
        new_session_request(self.address, self.desired_caps)
        new_session_request(self.address, self.desired_caps)
        response = new_session_request(self.address, self.desired_caps)
        vm_count = self.server.platforms.vm_count
        self.assertEqual(2, vm_count)
        self.assertTrue("PlatformException: maximum count of virtual machines already running" in response.content)

    def test_delete_none_existing_session(self):
        session = uuid4()
        response = delete_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" % session in response.content)

    def test_get_none_existing_session(self):
        session = uuid4()
        response = get_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" % session in response.content)


class TestTimeoutSession(unittest.TestCase):
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
        Session.timeouted = False
        del self.server

    def test_server_delete_timeouted_session(self):
        Session.timeouted = True

        self.assertEqual(0, self.server.platforms.vm_count)

        response = new_session_request(self.address, self.desired_caps)
        vm_count = self.server.platforms.vm_count

        self.assertEqual(0, vm_count)
        self.assertTrue("TimeoutException" in response.content)


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
        new_session_request(self.address, self.desired_caps)

        sessions = self.server.sessions.map
        self.assertEqual(1, len(sessions))

        del self.server
        self.assertEqual(0, len(sessions))

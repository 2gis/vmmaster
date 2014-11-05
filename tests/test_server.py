import unittest
import json
import time
from uuid import uuid4
from threading import Thread
import socket

from mock import Mock, patch
from nose.twistedtools import reactor

from vmmaster.core.config import setup_config

# Mocking
def session_id(*args, **kwargs):
    class Session(object):
        id = uuid4()
    return Session()
from vmmaster.core import db
db.database = Mock(create_session=Mock(side_effect=session_id))
from vmmaster.core import connection
connection.Virsh.__new__ = Mock()
from vmmaster.core.network import network
network.Network.__new__ = Mock()
from vmmaster.core.platform_server import PlatformHandler, Request
PlatformHandler.take_screenshot = Mock()
from vmmaster.core.virtual_machine.clone import Clone
Clone.clone_origin = Mock()
Clone.define_clone = Mock()
Clone.start_virtual_machine = Mock()
Clone.drive_path = Mock()
from vmmaster.core import commands
commands.ping_vm = Mock(__name__="check_vm_online")
commands.selenium_status = Mock(__name__="check_vm_online")
commands.start_selenium_session = Mock(__name__="start_selenium_session", return_value=(200, {}, json.dumps({'sessionId':"1"})))
from vmmaster.core.utils import utils
utils.delete_file = Mock()

from vmmaster.server import VMMasterServer
from vmmaster.core.utils.network_utils import get_socket
from vmmaster.core.sessions import Session
from vmmaster.core.virtual_machine.virtual_machines_pool import VirtualMachinesPool


def request(host, method, url, headers=None, body=None):
    if headers is None:
        headers = dict()
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


def request_with_drop(address, desired_caps):
    dc = json.dumps(desired_caps)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.connect(address)

    req = "POST /wd/hub/session HTTP/1.1\r\n" +\
    "Content-Length: %s\r\n" % len(dc) +\
    "\r\n" +\
    "%s\r\n" % dc

    s.send(req)
    s.close()


def new_session_request(address, desired_caps):
    return request("%s:%s" % address, "POST", "/wd/hub/session", body=json.dumps(desired_caps))


def delete_session_request(address, session):
    return request("%s:%s" % address, "DELETE", "/wd/hub/session/%s" % str(session))


def get_session_request(address, session):
    return request("%s:%s" % address, "GET", "/wd/hub/session/%s" % str(session))


def run_script(address, session, script):
    return request("%s:%s" % address, "POST", "/wd/hub/session/%s/runScript" % str(session), body=json.dumps(
        {"script": script}
    ))


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
        del self.server

    def test_server_create_new_session(self):
        response = new_session_request(self.address, self.desired_caps)
        vm_count = len(VirtualMachinesPool.using)
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    def test_server_maximum_vm_running(self):
        from vmmaster.core.session_queue import q
        new_session_request(self.address, self.desired_caps)
        new_session_request(self.address, self.desired_caps)
        t = Thread(target=new_session_request, args=(self.address, self.desired_caps))
        t.daemon = True
        self.assertEqual(0, len(q))
        with patch.object(VirtualMachinesPool, 'can_produce') as mock:
            t.start()
            while not mock.called:
                time.sleep(0.1)
        self.assertEqual(2, len(VirtualMachinesPool.using))
        self.assertEqual(1, len(q))

    def test_delete_session(self):
        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        with patch.object(Session, 'make_request', side_effect=Mock(return_value=(200, {}, None))):
            response = delete_session_request(self.address, session_id)
        self.assertEqual(200, response.status)

    def test_delete_none_existing_session(self):
        session = uuid4()
        response = delete_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" % session in response.content)

    def test_get_none_existing_session(self):
        session = uuid4()
        response = get_session_request(self.address, session)
        self.assertTrue("SessionException: There is no active session %s" % session in response.content)

    def test_server_client_connection_drop(self):
        with patch.object(Request, 'input_stream', return_result=Mock(_wrapped=Mock(closed=True))):
            with patch.object(Session, 'delete') as mock:
                new_session_request(self.address, self.desired_caps)

        self.assertTrue(mock.called)

    def test_run_script(self):
        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        output = json.dumps({"output": "hello world\n"})
        with patch.object(commands, 'Commands', {'runScript': Mock(return_value=(200, {}, output))}):
            response = run_script(self.address, session_id, "echo 'hello world'")
        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)


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
        del self.server

    def test_server_delete_timeouted_session(self):
        self.assertEqual(0, VirtualMachinesPool.count())

        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        session = self.server.sessions.get_session(session_id)
        session.timeout()
        vm_count = len(VirtualMachinesPool.using)

        self.assertEqual(0, vm_count)
        response = get_session_request(self.address, session_id)
        self.assertTrue("SessionException: There is no active session %s" % session_id in response.content,
                        "SessionException: There is no active session %s not in %s" % (session_id, response.content))


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

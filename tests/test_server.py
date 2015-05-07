import unittest
import json
from uuid import uuid4
from threading import Thread
from multiprocessing.pool import ThreadPool
import socket

from mock import Mock, patch
from nose.twistedtools import reactor

import time
from vmmaster.core.config import setup_config

from helpers import wait_for


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
network.Network = Mock(name='Network')
from vmmaster.core.virtual_machine.clone import KVMClone
KVMClone.clone_origin = Mock()
KVMClone.define_clone = Mock()
KVMClone.start_virtual_machine = Mock()
KVMClone.drive_path = Mock()
from vmmaster.webdriver import commands
commands.ping_vm = Mock(__name__="check_vm_online")
commands.selenium_status = Mock(__name__="selenium_status",
                                return_value=(200, {}, json.dumps({'status': 0})))
commands.start_selenium_session = Mock(__name__="start_selenium_session",
                                       return_value=(200, {}, json.dumps({'sessionId': "1"})))
from vmmaster.webdriver.helpers import Request
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


def request_with_drop(address, desired_caps, method=None):
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
    if method is not None:
        method()
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


def vmmaster_label(address, session, label=None):
    return request("%s:%s" % address, "POST", "/wd/hub/session/%s/vmmasterLabel" % str(session), body=json.dumps(
        {"label": label}
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


def server_is_down(address):
    s = get_socket(address[0], address[1])
    time_start = time.time()
    timeout = 5
    while s:
        s = get_socket(address[0], address[1])
        time.sleep(0.1)
        if time.time() - time_start > timeout:
            raise RuntimeError("server is running on %s:%s" % address)


class TestServer(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.server.app.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)

    def tearDown(self):
        del self.server
        server_is_down(self.address)

    def test_server_create_new_session(self):
        response = new_session_request(self.address, self.desired_caps)
        vm_count = len(VirtualMachinesPool.using)
        self.assertEqual(200, response.status)
        self.assertEqual(1, vm_count)

    def test_server_create_new_session_with_dc(self):
        # Let's do it with user/token
        _desired_caps = self.desired_caps.copy()
        _desired_caps["desiredCapabilities"]["user"] = "anonymous"
        _desired_caps["desiredCapabilities"]["token"] = None
        response = new_session_request(self.address, _desired_caps)
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
        t.start()
        wait_for(lambda: len(q) > 0)
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

    def test_server_deleting_session_on_client_connection_drop(self):
        response = new_session_request(self.address, self.desired_caps)
        session = json.loads(response.content)["sessionId"].encode("utf-8")

        with patch.object(Request, 'input_stream', return_result=Mock(_wrapped=Mock(closed=True))):
            with patch.object(Session, 'delete') as mock:
                get_session_request(self.address, session)
        self.assertTrue(mock.called)

    def test_run_script(self):
        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        output = json.dumps({"output": "hello world\n"})
        with patch.object(commands, 'AgentCommands', {'runScript': Mock(return_value=(200, {}, output))}):
            response = run_script(self.address, session_id, "echo 'hello world'")
        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    def test_vmmaster_label(self):
        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")
        output = json.dumps({"value": "step-label"})
        with patch.object(commands, 'InternalCommands', {'vmmasterLabel': Mock(return_value=(200, {}, output))}):
            response = vmmaster_label(self.address, session_id, "step-label")
        self.assertEqual(200, response.status)
        self.assertEqual(output, response.content)

    def test_vmmaster_no_such_platform(self):
        desired_caps = {
            'desiredCapabilities': {
                'platform': 'no_platform'
            }
        }
        response = new_session_request(self.address, desired_caps)
        error = json.loads(response.content).get('value')
        self.assertTrue('PlatformException("no such platform")' in error, error)


class TestTimeoutSession(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.server.app.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)

    def tearDown(self):
        del self.server
        server_is_down(self.address)

    def test_server_delete_timeouted_session(self):
        self.assertEqual(0, VirtualMachinesPool.count())

        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        session = self.server.app.sessions.get_session(session_id)
        session.timeout()
        vm_count = len(VirtualMachinesPool.using)

        self.assertEqual(0, vm_count)
        response = get_session_request(self.address, session_id)
        self.assertTrue("SessionException: There is no active session %s" % session_id in response.content,
                        "SessionException: There is no active session %s not in %s" % (session_id, response.content))

    def test_server_delete_closed_session(self):
        self.assertEqual(0, VirtualMachinesPool.count())
        response = new_session_request(self.address, self.desired_caps)
        session_id = json.loads(response.content)["sessionId"].encode("utf-8")

        session = self.server.app.sessions.get_session(session_id)
        session.close()
        vm_count = len(VirtualMachinesPool.using)

        self.assertEqual(0, vm_count)
        response = get_session_request(self.address, session_id)
        self.assertTrue("SessionException: There is no active session %s" % session_id in response.content,
                        "SessionException: There is no active session %s not in %s" % (session_id, response.content))

    def test_req_closed_during_session_creating(self):
        def method():
            while True:
                try:
                    if len(self.server.app.sessions.map) == 1:
                        # close the connection when the session was created
                        break
                except:
                    pass

        self.assertEqual(0, VirtualMachinesPool.count())
        request_with_drop(self.address, self.desired_caps, method)
        time.sleep(2)  # waiting for vmmaster response
        vm_count = len(VirtualMachinesPool.using)
        self.assertEqual(0, vm_count)
        self.assertEqual(0, len(self.server.app.sessions.map))

    def test_req_closed_when_request_append_to_queue(self):
        def method():
            while True:
                try:
                    if len(self.server.app.queue) == 1:
                        # close the connection when the request is queued
                        break
                except:
                    pass

        self.assertEqual(0, VirtualMachinesPool.count())
        request_with_drop(self.address, self.desired_caps, method)
        time.sleep(2)  # waiting for vmmaster response
        vm_count = len(VirtualMachinesPool.using)
        self.assertEqual(0, vm_count)
        self.assertEqual(0, len(self.server.app.sessions.map))


class TestServerShutdown(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.server.app.platforms.platforms.keys()[0]
            }
        }
        server_is_up(self.address)

    def test_server_shutdown(self):
        del self.server

    def test_server_shutdown_delete_sessions(self):
        new_session_request(self.address, self.desired_caps)

        sessions = self.server.app.sessions.map
        self.assertEqual(1, len(sessions))

        del self.server
        self.assertEqual(0, len(sessions))

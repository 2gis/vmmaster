import unittest
import time
import json
from uuid import uuid4

from mock import Mock

# Mocking
from vmmaster.core import db
def session_id(*args, **kwargs):
    class Session(object):
        id = uuid4()
    return Session()

db.database = Mock(create_session=Mock(side_effect=session_id))
from vmmaster.core import connection
connection.Virsh.__new__ = Mock()
from vmmaster.core.network import network
network.Network.__new__ = Mock()

from vmmaster.server import create_app

from vmmaster.core.config import setup_config, config
from vmmaster.core.utils.network_utils import get_socket
from vmmaster.core.virtual_machine import VirtualMachine


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


def api_sessions_request(address):
    return request("%s:%s" % address, "GET", "/api/sessions")


def api_stop_session_request(address, session_id):
    return request("%s:%s" % address, "POST", "/api/session/%s/stop" % session_id)


def api_platforms_request(address):
    return request("%s:%s" % address, "GET", "/api/platforms")


def server_is_up(address):
    s = get_socket(address[0], address[1])
    time_start = time.time()
    timeout = 5
    while not s:
        s = get_socket(address[0], address[1])
        time.sleep(0.1)
        if time.time() - time_start > timeout:
            raise RuntimeError("server is not running on %s:%s" % address)


class TestApi(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.app = create_app()
        self.client = self.app.test_client()
        self.platforms = self.app.platforms.platforms
        self.platform = self.platforms.keys()[0]
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }

    def tearDown(self):
        self.app.cleanup()

    def test_api_sessions(self):
        self.app.sessions.start_session("session1", self.platform, VirtualMachine())
        self.app.sessions.start_session("session2", self.platform, VirtualMachine())
        response = self.client.get('/api/sessions')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        sessions = body['result']['sessions']
        self.assertEqual(2, len(sessions))
        for session in sessions:
            self.assertEqual(self.platform, session['platform'])
        self.assertEqual(200, body['metacode'])

    def test_api_platforms(self):
        response = self.client.get('/api/platforms')
        body = json.loads(response.data)
        self.assertEqual(200, response.status_code)
        platforms = body['result']['platforms']
        self.assertEqual(2, len(platforms))
        names = [platform for platform in self.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    def test_api_stop_session(self):
        session = self.app.sessions.start_session("session1", self.platform, VirtualMachine())
        response = self.client.post("/api/session/%s/stop" % session.id)
        body = json.loads(response.data)
        self.assertEqual(200, body['metacode'])
        self.assertEqual(0, len(self.app.sessions.map))
import unittest
import time
import json
from uuid import uuid4

from nose.twistedtools import reactor

from mock import Mock

# Mocking
from vmmaster.core import db
database_mock = Mock()
def session_id(*args, **kwargs):
    class Session(object):
        id = uuid4()
    return Session()
db.database = Mock(createSession=Mock(side_effect=session_id))
from vmmaster.core import connection
connection.Virsh.__new__ = Mock()
from vmmaster.core.network import network
network.Network.__new__ = Mock()


from vmmaster.core.config import setup_config, config
from vmmaster.server import VMMasterServer
from vmmaster.core.utils.network_utils import get_socket


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


class TestCloneList(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        self.address = ("localhost", 9000)
        self.server = VMMasterServer(reactor, self.address[1])
        self.platform = self.server.platforms.platforms.keys()[0]
        self.desired_caps = {
            'desiredCapabilities': {
                'platform': self.platform
            }
        }
        server_is_up(self.address)

    def tearDown(self):
        del self.server

    def test_api_sessions(self):
        self.server.sessions.start_session("session1", self.platform)
        self.server.sessions.start_session("session2", self.platform)
        response = api_sessions_request(self.address)
        body = json.loads(response.content)
        self.assertEqual(200, response.status)
        sessions = body['result']['sessions']
        self.assertEqual(2, len(sessions))
        for session in sessions:
            self.assertEqual(self.platform, session['platform'])
        self.assertEqual(200, body['metacode'])

    def test_api_platforms(self):
        response = api_platforms_request(self.address)
        body = json.loads(response.content)
        self.assertEqual(200, response.status)
        platforms = body['result']['platforms']
        self.assertEqual(2, len(platforms))
        names = [platform for platform in self.server.platforms.platforms]
        self.assertEqual(names, platforms)
        self.assertEqual(200, body['metacode'])

    def test_api_stop_session(self):
        session = self.server.sessions.start_session("session1", self.platform)
        response = api_stop_session_request(self.address, session.id)
        body = json.loads(response.content)
        self.assertEqual(200, body['metacode'])
        self.assertEqual(0, len(self.server.sessions.map))
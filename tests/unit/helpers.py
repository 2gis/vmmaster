# coding: utf-8

import BaseHTTPServer
import copy
import json
import os
import threading
import time
import socket
import unittest
from Queue import Queue, Empty

from mock import Mock, patch, PropertyMock
from nose.twistedtools import reactor

from core.utils.network_utils import get_socket
from twisted.internet.defer import Deferred, TimeoutError
from twisted.python.failure import Failure


class TimeoutException(Exception):
    pass


def wait_for(condition, timeout=10):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)

    return condition()


def request(host, method, url, headers=None, body=None):
    if headers is None:
        headers = dict()
    import httplib
    conn = httplib.HTTPConnection(host, timeout=20)
    conn.request(method=method, url=url, headers=headers, body=body)
    response = conn.getresponse()

    class Response(object):
        pass
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


def new_session_request(client, desired_caps):
    return client.post("/wd/hub/session", data=json.dumps(desired_caps))


def delete_session_request(client, session):
    return client.delete("/wd/hub/session/%s" % str(session))


def get_session_request(client, session):
    return client.get("/wd/hub/session/{}".format(session))


def run_script(client, session, script):
    return client.post(
        "/wd/hub/session/%s/vmmaster/runScript" % str(session),
        data=json.dumps({"script": script})
    )


def vmmaster_label(client, session, label=None):
    return client.post(
        "/wd/hub/session/%s/vmmaster/vmmasterLabel" % str(session),
        data=json.dumps({"label": label})
    )


def server_is_up(address, wait=5):
    s = get_socket(address[0], address[1])
    time_start = time.time()
    timeout = wait
    while not s:
        s = get_socket(address[0], address[1])
        time.sleep(0.1)
        if time.time() - time_start > timeout:
            raise RuntimeError("server is not running on %s:%s" % address)


def server_is_down(address, wait=5):
    s = get_socket(address[0], address[1])
    time_start = time.time()
    timeout = wait
    while s:
        s = get_socket(address[0], address[1])
        time.sleep(0.1)
        if time.time() - time_start > timeout:
            raise RuntimeError("server is running on %s:%s" % address)


def fake_home_dir():
    return '%s/data' % os.path.dirname(__file__)


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    @property
    def body(self):
        """get request body."""
        data = copy.copy(self.rfile)

        if self.headers.getheader('Content-Length') is None:
            body = None
        else:
            content_length = int(self.headers.getheader('Content-Length'))
            body = data.read(content_length)

        return body

    def send_reply(self, code, headers, body):
        """ Send reply to client. """
        # reply code
        self.send_response(code)

        # reply headers
        for keyword, value in headers.iteritems():
            self.send_header(keyword, value)
        self.end_headers()

        # reply body
        self.wfile.write(body)

    def do_POST(self):
        reply = self.headers.getheader("reply")
        code = int(reply)
        self.send_reply(code, self.headers.dict, body=self.body)

    def do_GET(self):
        body = "ok"
        self.send_reply(200, {"Content-Length": len(body)}, body)

    def log_error(self, format, *args):
        pass

    def log_message(self, format, *args):
        pass

    def log_request(self, code='-', size='-'):
        pass


class ServerMock(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._server = BaseHTTPServer.HTTPServer((host, port), Handler)
        self._server.timeout = 1
        self._server.allow_reuse_address = True
        self._thread = threading.Thread(target=self._server.serve_forever)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


class BaseTestCase(unittest.TestCase):
    def shortDescription(self):
        return None


primary_key_mock = 1


def set_primary_key(_self):
    global primary_key_mock
    _self.id = primary_key_mock
    primary_key_mock += 1
    pass


class DatabaseMock(Mock):
    active_sessions = {}

    def __init__(self, *args, **kwargs):
        super(DatabaseMock, self).__init__(*args, **kwargs)
        self.add = Mock(side_effect=set_primary_key)

    def get_active_sessions(self):
        return self.active_sessions.values()

    def get_session(self, session_id):
        return self.active_sessions.get(str(session_id))

    @staticmethod
    def get_last_session_step(session_id):
        return Mock()


def custom_wait(self, method):
    self.ready = True
    self.checking = False


def vmmaster_server_mock(port):
    mocked_image = Mock(
        id=1, status='active',
        get=Mock(return_value='snapshot'),
        min_disk=20,
        min_ram=2,
        instance_type_flavorid=1,
    )
    type(mocked_image).name = PropertyMock(
        return_value='test_origin_1')

    with patch(
        'core.db.Database', DatabaseMock()
    ), patch(
        'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
    ), patch(
        'core.logger.setup_logging', Mock(return_value=Mock())
    ), patch(
        'core.sessions.SessionWorker', Mock()
    ), patch.multiple(
        'vmpool.platforms.OpenstackPlatforms',
        images=Mock(return_value=[mocked_image]),
        flavor_params=Mock(return_value={'vcpus': 1, 'ram': 2}),
        limits=Mock(return_value={
            'maxTotalCores': 10, 'maxTotalInstances': 10,
            'maxTotalRAMSize': 100, 'totalCoresUsed': 0,
            'totalInstancesUsed': 0, 'totalRAMUsed': 0}),
    ), patch.multiple(
        'core.utils.openstack_utils',
        nova_client=Mock(return_value=Mock())
    ), patch.multiple(
        'vmpool.clone.OpenstackClone',
        _wait_for_activated_service=custom_wait,
        ping_vm=Mock(return_value=True)
    ):
        from vmmaster.server import VMMasterServer
        return VMMasterServer(reactor, port)


def request_mock(**kwargs):
    return Mock(status_code=200, headers={}, content=json.dumps({'status': 0}))


def wait_deferred(d, timeout=5):
    _q = Queue()
    if not isinstance(d, Deferred):
        return None
    d.addBoth(_q.put)
    try:
        ret = _q.get(timeout is not None, timeout)
    except Empty:
        raise TimeoutError
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret

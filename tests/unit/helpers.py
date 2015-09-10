# coding: utf-8
import BaseHTTPServer
import copy
import json
import os
import threading
import time
import socket
import unittest

from mock import Mock, patch


class TimeoutException(Exception):
    pass


def wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)

    return condition()


def request(host, method, url, headers=None, body=None):
    if headers is None:
        headers = dict()
    import httplib
    conn = httplib.HTTPConnection(host)
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


def new_session_request(address, desired_caps):
    return request("%s:%s" % address, "POST",
                   "/wd/hub/session", body=json.dumps(desired_caps))


def delete_session_request(address, session):
    return request("%s:%s" % address, "DELETE",
                   "/wd/hub/session/%s" % str(session))


def get_session_request(address, session):
    return request("%s:%s" % address, "GET",
                   "/wd/hub/session/%s" % str(session))


def run_script(address, session, script):
    return request("%s:%s" % address, "POST",
                   "/wd/hub/session/%s/runScript" % str(session),
                   body=json.dumps({"script": script}))


def vmmaster_label(address, session, label=None):
    return request("%s:%s" % address, "POST",
                   "/wd/hub/session/%s/vmmasterLabel" % str(session),
                   body=json.dumps({"label": label}))

from core.utils.network_utils import get_socket


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
        self._thread.join(1)


class BaseTestCase(unittest.TestCase):
    def shortDescription(self):
        return None


def vmmaster_server_mock(port):
    with patch(
        'core.network.network.Network', Mock(
            return_value=Mock(get_ip=Mock(return_value='0')))
    ), patch(
        'core.connection.Virsh', Mock()
    ), patch(
        'core.db.database', Mock()
    ), patch(
        'core.utils.init.home_dir', Mock(return_value=fake_home_dir())
    ), patch(
        'core.logger.setup_logging', Mock(return_value=Mock())
    ), patch(
        'core.sessions.SessionWorker', Mock()
    ):
        from vmmaster.server import VMMasterServer
        from nose.twistedtools import reactor
        return VMMasterServer(reactor, port)

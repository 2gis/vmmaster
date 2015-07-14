# coding: utf-8
import json
import os
import time
import socket


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

from vmmaster.core.utils.network_utils import get_socket


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
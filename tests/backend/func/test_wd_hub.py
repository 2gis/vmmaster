# coding: utf-8

import ujson
from asyncio import coroutine
from mock import patch
from backend.sessions import Session
from backend.app import app as backend_app


BASE_SESSION_URI = '/wd/hub/session'
BASE_VMMASTER_URI = '/wd/hub/vmmaster'
CREATE_SESSION_DC = {
    "browserName": "chrome",
    "version": "ANY",
    "name": "TestPositiveCase",
    "platform": "ubuntu-14.04-x64"
}
CREATE_SESSION_DATA = '{"desiredCapabilities": %s}' % ujson.dumps(CREATE_SESSION_DC)


async def success_mock_request(*args, **kwargs):
    return 200, "{}", '{"sessionId": 1}'


def _app(loop):
    with patch(
        'backend.queue_producer.AsyncQueueProducer.connect', new=coroutine(lambda a: None)
    ):
        return backend_app(loop=loop, CONFIG='settings')


async def test_create_session(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)

        session_response = await client.post(BASE_SESSION_URI, data=CREATE_SESSION_DATA)
        assert session_response.status == 200
        session_text = await session_response.text()
        assert ujson.loads(session_text) == {"sessionId": 1}


async def test_get_session(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        get_response = await client.get("%s/1" % BASE_SESSION_URI)
        assert get_response.status == 200
        get_text = await get_response.text()
        get_text = ujson.loads(get_text)
        assert ujson.loads(get_text["session"]["dc"]) == CREATE_SESSION_DC


async def test_delete_session(test_client):
    with patch(
        'backend.queue_producer.AsyncQueueProducer.add_msg_to_queue', new=coroutine(lambda a, b, c: None)
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        delete_response = await client.delete("%s/1" % BASE_SESSION_URI)
        assert delete_response.status == 200
        delete_text = await delete_response.text()
        assert delete_text == "Session 1 closed"


async def test_delete_proxy_request(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        proxy_response = await client.delete("%s/1/cookie" % BASE_SESSION_URI)
        assert proxy_response.status == 200
        proxy_text = await proxy_response.text()
        assert ujson.loads(proxy_text) == {"sessionId": 1}


async def test_get_proxy_request(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        proxy_response = await client.get("%s/1/cookie" % BASE_SESSION_URI)
        assert proxy_response.status == 200
        proxy_text = await proxy_response.text()
        assert ujson.loads(proxy_text) == {"sessionId": 1}


async def test_post_proxy_request(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        proxy_response = await client.post("%s/1/element/2a3s4d567/text" % BASE_SESSION_URI, data=CREATE_SESSION_DATA)
        assert proxy_response.status == 200
        proxy_text = await proxy_response.text()
        assert ujson.loads(proxy_text) == {"sessionId": 1}


async def test_agent_command_request(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        proxy_response = await client.post("%s/runScript/session/1" % BASE_VMMASTER_URI, data=CREATE_SESSION_DATA)
        assert proxy_response.status == 200
        proxy_text = await proxy_response.text()
        assert proxy_text == "agent command 1"


async def test_vmmaster_command_request(test_client):
    with patch(
            'backend.sessions.Session.make_request', new=success_mock_request
    ):
        client = await test_client(_app)
        session = Session(id=1, dc=CREATE_SESSION_DC)
        client.app.sessions[session.id] = session

        proxy_response = await client.post("%s/vmmasterLabel/session/1" % BASE_VMMASTER_URI, data=CREATE_SESSION_DATA)
        assert proxy_response.status == 200
        proxy_text = await proxy_response.text()
        assert proxy_text == "vmmaster command 1"

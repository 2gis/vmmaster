# coding: utf-8
import ujson
from asyncio import coroutine
from mock import patch
from backend.app import app as backend_app


def _app(loop):
    with patch(
        'backend.queue_producer.AsyncQueueProducer.connect', new=coroutine(lambda a: None)
    ):
        return backend_app(loop=loop, CONFIG='config.tests')


async def test_api_get_sessions(test_client):
    dct = {1: {"id": 1}}
    client = await test_client(_app)
    client.app.sessions = dct

    response = await client.get("/api/sessions")

    assert response.status == 200
    text = await response.text()
    assert ujson.dumps(dct) == text


async def test_api_get_messages(test_client):
    dct = {1: {"request": "bla bla", "response": None}}
    client = await test_client(_app)
    client.app.queue_producer.messages = dct

    response = await client.get("/api/messages")

    assert response.status == 200
    text = await response.text()
    assert ujson.dumps(dct) == text

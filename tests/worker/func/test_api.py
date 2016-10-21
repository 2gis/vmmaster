# coding: utf-8
import ujson
from asyncio import coroutine
from mock import patch
from worker.app import app as worker_app


def _app(loop):
    with patch(
        'worker.queue_consumer.AsyncQueueConsumer.connect', new=coroutine(lambda a: None)
    ), patch(
        'worker.app.on_shutdown', new=coroutine(lambda a: None)
    ):
        return worker_app(loop=loop, CONFIG='settings')


async def test_api_get_sessions(test_client):
    dct = {"1": {"id": 1}}
    client = await test_client(_app)
    client.app.sessions = dct

    response = await client.get("/api/sessions")

    assert response.status == 200
    text = await response.text()
    assert dct == ujson.loads(text)


async def test_api_get_messages(test_client):
    dct = {
        "platforms": dict(),
        "sessions": dict(),
        "services": dict()
    }
    client = await test_client(_app)
    client.app.queue_consumer.messages = dct

    response = await client.get("/api/messages")

    assert response.status == 200
    text = await response.text()
    assert dct == ujson.loads(text)


async def test_api_get_platforms(test_client):
    dct = {"ubuntu-14.04-x64": 2}
    client = await test_client(_app)
    with patch(
            'core.database.Database.get_platforms', new=coroutine(lambda a, b: dct)
    ):
        response = await client.get("/api/platforms")

    assert response.status == 200
    text = await response.text()
    assert dct == ujson.loads(text)


async def test_api_get_channels(test_client):
    dct = {"1": {"consumer_tag": "ctag1.12345678", "channel": "<Mock>"}}
    client = await test_client(_app)
    client.app.queue_consumer.channels = dct

    response = await client.get("/api/channels")

    assert response.status == 200
    text = await response.text()
    assert dct == ujson.loads(text)

# coding: utf-8
import ujson
from backend.app import app as backend_app


async def test_api_get_sessions(test_client):
    dct = {1: {"id": 1}}
    client = await test_client(backend_app)
    client.app.sessions = dct

    response = await client.get("/api/sessions")

    assert response.status == 200
    text = await response.text()
    assert ujson.dumps(dct) == text


async def test_api_get_messages(test_client):
    dct = {1: {"request": "bla bla", "response": None}}
    client = await test_client(backend_app)
    client.app.queue_producer.messages = dct

    response = await client.get("/api/messages")

    assert response.status == 200
    text = await response.text()
    assert ujson.dumps(dct) == text

# coding: utf-8


async def start_session(msg):
    msg["status"] = 200
    msg["headers"] = '{"Content-Length": 123}'
    msg["content"] = '{"sessionId": "123qwe"}'
    return msg


async def make_request_for_session(msg):
    # do anything
    return msg


async def make_service_command(msg):
    # do anything
    return msg

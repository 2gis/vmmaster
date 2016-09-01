# coding: utf-8

import os
import time
import ujson
import asyncio
import logging


log = logging.getLogger(__name__)


def wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)

    return condition()


def generator_wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)
        yield None

    yield condition()


async def async_wait_for(condition, loop, timeout=5):
    start = loop.time()
    while not condition() and loop.time() - start < timeout:
        await asyncio.sleep(0.1)

    return condition()


def to_json(result):
    try:
        return ujson.loads(result)
    except ValueError:
        log.info("Couldn't parse response content <%s>" % repr(result))
        return {}


def home_dir():
    return os.path.abspath(os.curdir)

# coding: utf-8

import importlib

import os
import time
import ujson
import asyncio
import logging
from contextlib import contextmanager


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
        await asyncio.sleep(0.1, loop=loop)

    return condition()


def to_json(result):
    try:
        return ujson.loads(result)
    except ValueError:
        log.info("Couldn't parse response content <%s>" % repr(result))
        return {}


def home_dir():
    return os.path.abspath(os.curdir)


class Struct(dict):

    """ `Attribute` dictionary. Use attributes as keys. """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("Attribute '%s' doesn't exists. " % name)

    def __setattr__(self, name, value):
        self[name] = value


class LStruct(Struct):

    """ Locked structure. Used as application/plugins settings.

    Going to be immutable after application is started.

    """

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, '_lock', False)
        super().__init__(*args, **kwargs)

    def lock(self):
        object.__setattr__(self, '_lock', True)

    def __setitem__(self, name, value):
        if self._lock:
            raise RuntimeError('`%s` is locked.' % type(self))
        super().__setitem__(name, value)


def make_path(path, url_prefix=None):
    return ('/'.join((url_prefix.rstrip('/'), path.lstrip('/')))
            if url_prefix
            else path)


@contextmanager
def add_route_context(app, module, url_prefix=None, name_prefix=None):
    if isinstance(module, (str, bytes)):
        module = importlib.import_module(module)

    def add_route(method, path, handler, name=None):
        """
        :param str method: HTTP method.
        :param str path: Path for the route.
        :param handler: A handler function or a name of a handler function contained
            in `module`.
        :param str name: Name for the route. If `None`, defaults to the handler's
            function name.
        """
        if isinstance(handler, (str, bytes)):
            if not module:
                raise ValueError(
                    'Must pass module to add_route_context if passing handler name strings.'
                )
            name = name or handler
            handler = getattr(module, handler)
        else:
            name = name or handler.__name__
        path = make_path(path, url_prefix)
        name = '.'.join((name_prefix, name)) if name_prefix else name
        return app.router.add_route(method, path, handler, name=name)
    yield add_route


def make_request_body(data):
    return ujson.dumps(data).encode('utf-8')

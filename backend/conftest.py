# coding: utf-8

import asyncio
import pytest
from aiohttp import ClientSession, test_utils
from backend.app import create_app

#
# @pytest.yield_fixture
# def create_server(loop):
#     app = handler = srv = None
#
#     @asyncio.coroutine
#     def create(*, debug=False, ssl_ctx=None, proto='http'):
#         nonlocal app, handler, srv
#         app = create_app(loop=loop)
#         port = test_utils.unused_port()
#         handler = app.make_handler(debug=debug, keep_alive_on=False)
#         srv = yield from loop.create_server(handler, '127.0.0.1', port,
#                                             ssl=ssl_ctx)
#         if ssl_ctx:
#             proto += 's'
#         url = "{}://127.0.0.1:{}".format(proto, port)
#         return app, url
#
#     yield create
#
#     @asyncio.coroutine
#     def finish():
#         if srv:
#             srv.close()
#             yield from srv.wait_closed()
#         if app:
#             yield from app.shutdown()
#         if handler:
#             yield from handler.finish_connections()
#         if app:
#             yield from app.cleanup()
#
#     loop.run_until_complete(finish())


class Client:
    def __init__(self, session, url):
        self._session = session
        if not url.endswith('/'):
            url += '/'
        self._url = url

    def close(self):
        self._session.close()

    def request(self, method, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        return self._session.request(method, url, **kwargs)

    def get(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        return self._session.get(url, **kwargs)

    def post(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        return self._session.post(url, **kwargs)

    def delete(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        return self._session.delete(url)

    def ws_connect(self, path, **kwargs):
        while path.startswith('/'):
            path = path[1:]
        url = self._url + path
        return self._session.ws_connect(url, **kwargs)


# @pytest.yield_fixture
# def test_client(loop, app):
#     client = test_utils.TestClient(app)
#     loop.run_until_complete(client.start_server())
#     yield client
#     loop.run_until_complete(client.close())


# @pytest.yield_fixture
# def create_app_and_client(create_server, loop):
#     client = None
#
#     @asyncio.coroutine
#     def maker(*, server_params=None, client_params=None):
#         nonlocal client
#         if server_params is None:
#             server_params = {}
#         server_params.setdefault('debug', False)
#         server_params.setdefault('ssl_ctx', None)
#         app, url = yield from create_server(**server_params)
#         if client_params is None:
#             client_params = {}
#         client = Client(ClientSession(loop=loop, **client_params), url)
#         return app, client
#
#     yield maker
#     if client is not None:
#         client.close()

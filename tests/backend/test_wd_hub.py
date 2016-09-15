# coding: utf-8

from backend.app import app as backend_app


BASE_SESSION_URI = '/wd/hub/session'
CREATE_SESSION_DATA = {
    "desiredCapabilities": {
        "name": "TestPositiveCase",
        "platform": "ubuntu-14.04-x64",
        "browserName": "chrome",
        "version": "ANY"
    }
}


def _app(loop):
    return backend_app(loop=loop, CONFIG='config.tests')


# async def test_create_session(test_client):
#     client = await test_client(_app)
#     client.app.sessions = {}
#
#     session_response = await client.post(BASE_SESSION_URI, data=CREATE_SESSION_DATA)
#     assert session_response.status == 200
#     session_text = await session_response.text()
#     assert session_text
#
#     get_response = await client.get('%s/1' % BASE_SESSION_URI)
#     assert get_response.status == 200
#     get_text = await get_response.text()
#     assert get_text

import ujson
from backend.app import create_app


CREATE_SESSION_URI = '/wd/hub/session'
CREATE_SESSION_DATA = ujson.dumps({
    "desiredCapabilities": {
        "name": "TestPositiveCase",
        "platform": "ubuntu-14.04-x64",
        "browserName": "chrome",
        "version": ""
    }
})

# @pytest.fixture
# def app(loop):
#     from backend.app import create_app
#     return create_app(loop=loop)


async def test_create_session(test_client):
    client = await test_client(create_app)
    response = await client.post(CREATE_SESSION_URI, data=CREATE_SESSION_DATA)
    assert response.status == 200


# def test_get_session(test_client):
#     # client = yield from test_client()
#     response = test_client.get('/wd/hub/session/1')
#     assert response.text

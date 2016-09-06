import ujson


CREATE_SESSION_URI = '/wd/hub/session'
CREATE_SESSION_DATA = ujson.dumps({
    "desiredCapabilities": {
        "name": "TestPositiveCase",
        "platform": "ubuntu-14.04-x64",
        "browserName": "chrome",
        "version": ""
    }
})


def test_create_session(client):
    response = client.post(CREATE_SESSION_URI, CREATE_SESSION_DATA)
    assert response.status_code == 200


def test_get_session(client):
    response = client.get('/wd/hub/session/1')
    assert response.text

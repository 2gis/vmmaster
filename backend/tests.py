# tests


def test_create_session(client):
    response = client.post('/wd/hub/session', '{"desiredCapabilities": {"name": "TestPositiveCase", "javascriptEnabled": true, "takeScreenshot": "true", "platform": "ubuntu-14.04-x64", "browserName": "chrome", "version": ""}}')
    print(response.text)
    assert response.status_code == 200


def test_get_session(client):
    response = client.get('/wd/hub/session/1')
    assert response.json
    assert response.text == 'get session 1'

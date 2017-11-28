import time
import requests
from flask import Flask
from flask import render_template, request

from tests.functional.tests.config import Config

app = Flask(__name__)


@app.route('/')
@app.route('/index')
def index():
    user = {}
    return render_template('index.html', title='Home', user=user)


@app.route('/welldone', methods=['POST'])
def welldone():
    user = {'nickname': request.form['nickname']}
    if not user['nickname']:
        user = {}
    return render_template('index.html', title='Home', user=user)


@app.route('/long', methods=['GET', 'POST', 'DELETE'])
def long_request():
    try:
        response = requests.get("http://{}:{}/api/config".format(Config.host, Config.port)).json()
        request_timeout = response.get("result", {}).get("config", {}).get("REQUEST_TIMEOUT", 60)
        time.sleep(request_timeout + 1)
    except Exception as e:
        print("Can't sleep because: {}".format(e))
    return render_template('index.html', title='Long Request', user={})

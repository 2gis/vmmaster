from flask import Flask
from flask import render_template, request

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
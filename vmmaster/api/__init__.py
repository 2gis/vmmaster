# coding: utf-8

import json
import helpers

from flask import Blueprint, jsonify, request
from vmpool.api import helpers as vmpool_helpers
from core.auth.api_auth import auth
from core.config import config

api = Blueprint('api', __name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


@api.route('/status')
def status():
    return render_json({
        'sessions': helpers.get_sessions(),
        'queue': helpers.get_queue(),
        'platforms': vmpool_helpers.get_platforms(),
        'pool': vmpool_helpers.get_pool()
    })


@api.route('/platforms')
def platforms():
    return render_json(result={'platforms': vmpool_helpers.get_platforms()})


@api.route('/pool')
def pool():
    return render_json(result={'pool': vmpool_helpers.get_pool()})


@api.route('/pool_queue')
def queue():
    return render_json(result={'queue': vmpool_helpers.get_queue()})


@api.route('/config', methods=['GET', 'POST'])
def _config():
    if request.method == 'GET':
        c = {key: value for key, value in iter(config.__dict__.items())
             if not key.startswith("_")}
        return render_json(result={'config': c})
    else:
        new_config = json.loads(request.get_data())
        config.update(new_config)
        return render_json(result="success")


@api.route('/sessions')
def get_sessions():
    return render_json({'sessions': helpers.get_sessions()})


@api.route('/queue')
def get_queue():
    return render_json({'queue': helpers.get_queue()})


@api.route('/session/<int:session_id>')
def get_session(session_id):
    session = helpers.get_session(session_id)
    if session:
        return render_json(session.info)
    else:
        return render_json("Session %s not found" % session_id, 404)


@api.route('/session/<string:session_id>/stop', methods=['POST'])
def stop_session(session_id):
    _session = helpers.get_session(session_id)
    if _session:
        _session.failed()
        return render_json("Session %s closed successfully" % session_id, 200)
    else:
        return render_json("Session %s not found" % session_id, 404)


@api.route('/user/<int:user_id>', methods=['GET'])
@auth.login_required
def get_user(user_id):
    user = helpers.get_user(user_id)
    if user:
        return render_json(user.info)
    else:
        return render_json("User %s not found" % user_id, 404)


@api.route('/user/<int:user_id>/regenerate_token', methods=['POST'])
@auth.login_required
def regenerate_token(user_id):
    updated_user = helpers.regenerate_user_token(user_id)
    if updated_user:
        return render_json("Token for the user %s regenerated successfully "
                           % updated_user.username, 200)
    else:
        return render_json("User %s not found" % user_id, 404)

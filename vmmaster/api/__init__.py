# coding: utf-8
from flask import Blueprint, jsonify

import helpers


api = Blueprint('api', __name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


@api.route('/status')
def status():
    return render_json({
        'platforms': helpers.get_platforms(),
        'sessions': helpers.get_sessions(),
        'queue': helpers.get_queue(),
        'pool': helpers.get_pool()
    })


@api.route('/platforms')
def platforms():
    return render_json({'platforms': helpers.get_platforms()})


@api.route('/sessions')
def sessions():
    return render_json({'sessions': helpers.get_sessions()})


@api.route('/queue')
def queue():
    return render_json({'queue': helpers.get_queue()})


@api.route('/pool')
def pool():
    return render_json({'pool': helpers.get_pool()})


@api.route('/session/<int:session_id>')
def session(session_id):
    session = helpers.get_session(session_id)
    if session:
        return render_json(session.info)
    else:
        return render_json("Session %s not found" % session_id, 404)


@api.route('/session/<int:session_id>/stop')
def stop_session(session_id):
    session = helpers.get_session(session_id)
    if session:
        session.close()
        return render_json("Session %s closed successfully" % session_id, 200)
    else:
        return render_json("Session %s not found" % session_id, 404)
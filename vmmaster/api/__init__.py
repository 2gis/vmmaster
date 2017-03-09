# coding: utf-8

import json
import helpers
import logging

from flask import Blueprint, jsonify, request, current_app

from core import constants
from core.auth.api_auth import auth
from core.config import config

api = Blueprint('api', __name__)
log = logging.getLogger(__name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


@api.route('/version')
def version():
    from manage import version as get_version
    return render_json({'version': get_version()})


@api.route('/status')
def status():
    return render_json({
        'node': helpers.get_node_info(),
        'sessions': helpers.get_sessions(),
        'queue': helpers.get_queue()
    })


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
        _session.failed(reason=constants.SESSION_CLOSE_REASON_API_CALL)
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
    new_token = helpers.regenerate_user_token(user_id)
    if new_token:
        return render_json({'token': new_token}, 200)
    else:
        return render_json("User %s not found" % user_id, 404)


@api.route('/session/<string:session_id>/screenshots', methods=['GET'])
def get_screenshots(session_id):
    return render_json({'screenshots': helpers.get_screenshots(session_id)})


@api.route(
    '/session/<string:session_id>/step/<string:log_step_id>/screenshots',
    methods=['GET']
)
def get_screenshot_for_log_step(session_id, log_step_id):
    return render_json({
        'screenshots': helpers.get_screenshots(session_id, log_step_id)
    })


@api.route('/session/<int:session_id>/label/<int:label_id>/screenshots',
           methods=['GET'])
def get_screenshots_for_label(session_id, label_id):
    return render_json({
        'screenshots': helpers.get_screenshots_for_label(session_id, label_id)
    })


@api.route('/session/<int:session_id>/vnc_info', methods=['GET'])
def get_vnc_info(session_id):
    result, code = {}, 500

    _session = helpers.get_session(session_id)
    if _session and _session.endpoint.ip:
        if _session.vnc_helper.proxy:
            result, code = (
                {'vnc_proxy_port': _session.vnc_helper.get_proxy_port()}, 200
            )
        else:
            _session.vnc_helper.start_proxy()
            result, code = (
                {'vnc_proxy_port': _session.vnc_helper.get_proxy_port()}, 200
            )

    return render_json(result=result, code=code)


@api.route('/pool/<string:endpoint_name>', methods=['DELETE'])
def delete_vm_from_pool(endpoint_name):
    result = "Endpoint %s not found in pool" % endpoint_name

    endpoint = current_app.pool.get_by_name(endpoint_name)

    if endpoint:
        try:
            endpoint.delete()
            result = "Endpoint %s was deleted" % endpoint.name
        except Exception, e:
            log.info("Cannot delete vm %s through api method" % endpoint.name)
            result = "Got error during deleting vm %s. " \
                     "\n\n %s" % (endpoint.name, e.message)

    return render_json(result=result, code=200)


@api.route('/pool', methods=['DELETE'])
def delete_all_vm_from_pool():
    results = []
    failed = []

    for endpoint in current_app.pool.get_endpoints():
        try:
            endpoint.delete()
            results.append(endpoint)
        except:
            log.info("Cannot delete vm %s through api method" % endpoint.name)
            failed.append(endpoint)

    return render_json(result="This endpoints were deleted from "
                              "pool: %s" % results, code=200)

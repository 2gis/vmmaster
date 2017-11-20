# coding: utf-8

import json
import helpers
import logging
import os

from flask import Blueprint, jsonify, request

from core import constants
from core.auth.api_auth import auth
from core.config import config
from core.video import start_vnc_proxy
from core.utils import kill_process

api = Blueprint('api', __name__)
log = logging.getLogger(__name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


@api.route('/version')
def version():
    return render_json({'version': os.environ.get('APP_VERSION', 'unknown')})


@api.route('/status')
def status():
    return render_json({
        'providers': helpers.get_active_providers(),
        'sessions': helpers.get_sessions(),
        'queue': helpers.get_queue(),
        'platforms': helpers.get_platforms(),
        'endpoints': helpers.get_endpoints()
    })


@api.route('/endpoints')
def get_endpoints_from_active_providers():
    return render_json({
        'endpoints': helpers.get_endpoints()
    })


@api.route('/platforms')
def platforms():
    # TODO: test me
    return render_json(
        result={
            'platforms': helpers.get_platforms()
        }
    )


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
    vnc_proxy_port, code, _session = None, 500, helpers.get_session(session_id)

    if not _session or not _session.is_running:
        return render_json(result={}, code=code)

    if _session.vnc_proxy_port:
        return render_json(result={'vnc_proxy_port': _session.vnc_proxy_port}, code=200)

    (vnc_proxy_port, vnc_proxy_pid), code = start_vnc_proxy(_session.endpoint.ip, _session.endpoint.vnc_port), 200
    _session.refresh()

    if _session.closed:
        kill_process(vnc_proxy_pid)
        return render_json(result={}, code=500)

    if _session.vnc_proxy_port and _session.vnc_proxy_pid:
        kill_process(vnc_proxy_pid)
        vnc_proxy_port = _session.vnc_proxy_port
    else:
        log.info("VNC Proxy(pid:{}, port:{}) was started for {}".format(
            vnc_proxy_pid, vnc_proxy_port, _session)
        )
        _session.vnc_proxy_port, _session.vnc_proxy_pid = vnc_proxy_port, vnc_proxy_pid
        _session.save()

    return render_json(result={'vnc_proxy_port': vnc_proxy_port}, code=code)

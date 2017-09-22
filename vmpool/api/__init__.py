# coding: utf-8
import json

import helpers
import logging

from flask import Blueprint, jsonify, request, current_app
from core.config import config

api = Blueprint('api', __name__)
log = logging.getLogger(__name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


@api.route('/status')
def status():
    return render_json({
        'provider': helpers.get_provider_info(),
        'platforms': helpers.get_platforms(),
        'pool': helpers.get_pool()
    })


@api.route('/artifacts')
def artifacts():
    queue = helpers.get_artifact_collector_queue()
    return render_json({
        "amount": len(queue),
        "queue": queue
    })


@api.route('/platforms')
def platforms():
    return render_json(result={'platforms': helpers.get_platforms()})


@api.route('/pool')
def pool():
    return render_json(result={'pool': helpers.get_pool()})


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

    for endpoint in current_app.pool.active_endpoints:
        try:
            endpoint.delete()
            results.append(endpoint.name)
        except:
            log.info("Cannot delete vm %s through api method" % endpoint.name)
            failed.append(endpoint.name)

    return render_json(result="This endpoints were deleted from pool: %s" % results, code=200)

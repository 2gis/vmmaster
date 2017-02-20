# coding: utf-8

import helpers
import logging

from flask import Blueprint, jsonify, request, current_app

from vmpool.api import helpers

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
        'node': helpers.get_node_info(),
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

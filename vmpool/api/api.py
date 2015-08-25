import json
from flask import Blueprint, request

from vmmaster.core.config import config
import vmpool.api.helpers as helpers

api = Blueprint('api', __name__)


@api.route('/status')
def status():
    return helpers.render_json({
        'platforms': helpers.get_platforms(),
        'pool': helpers.get_pool(),
        'queue': helpers.get_queue()
    })


@api.route('/platforms')
def platforms():
    return helpers.render_json(result={'platforms': helpers.get_platforms()})


@api.route('/pool')
def pool():
    return helpers.render_json(result={'pool': helpers.get_pool()})


@api.route('/queue')
def queue():
    return helpers.render_json(result={'queue': helpers.get_queue()})


@api.route('/config', methods=['GET', 'POST'])
def _config():
    if request.method == 'GET':
        c = {key: value for key, value in iter(config.__dict__.items())
             if not key.startswith("_")}
        return helpers.render_json(result={'config': c})
    else:
        new_config = json.loads(request.get_data())
        config.update(new_config)
        return helpers.render_json(result="success")

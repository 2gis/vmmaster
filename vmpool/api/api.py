import helpers
from flask import Blueprint

api = Blueprint('api', __name__)


@api.route('/status')
def status():
    return helpers.render_json({
        'platforms': helpers.get_platforms(),
        'pool': helpers.get_pool()
    })


@api.route('/platforms')
def platforms():
    return helpers.render_json(result={'platforms': helpers.get_platforms()})


@api.route('/pool')
def pool():
    return helpers.render_json(result={'pool': helpers.get_pool()})
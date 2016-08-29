# coding: utf-8
import ujson
import logging
from muffin import Response


BASE_URL = '/api'
log = logging.getLogger(__name__)


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    response = ujson.dumps(response)
    return Response(body=response, content_type='application/json')

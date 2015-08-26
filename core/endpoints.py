# coding: utf-8
import time
import json

from core.utils import utils
from core.logger import log
from core.config import config


def get(dc):
    from core.sessions import RequestHelper

    log.info("Wait for endpoint answer (dc: %s)..." % str(dc))
    response = utils.make_request(
        RequestHelper(method='POST',
                      url="/endpoint/",
                      headers={'Content-Type': 'application/json'},
                      body=json.dumps(dc)),
        config.VM_POOL_HOST, config.VM_POOL_PORT)

    if response.status_code == 200:
        log.info('Got new endpoint (%s)' % response.content)
        endpoint = utils.to_json(response.content)

        return endpoint

    elif response.status_code == 404:
        raise Exception('No such endpoint '
                        'for your platform %s' % dc.get('platform'))
    else:
        raise Exception("Endpoint has not created")


def delete(endpoint_id):
    from core.sessions import RequestHelper
    request = RequestHelper(method='DELETE',
                            url="/endpoint/%s" % endpoint_id)
    log.debug('Request: %s' % request)
    utils.make_request(request, config.VM_POOL_HOST, config.VM_POOL_PORT)
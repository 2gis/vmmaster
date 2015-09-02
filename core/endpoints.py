# coding: utf-8

from core.logger import log
from vmpool.api.endpoint import new_vm, delete_vm


def get(dc):
    log.info("Wait for endpoint answer (dc: %s)..." % str(dc))
    endpoint = new_vm(dc)
    log.info('Got new endpoint (%s)' % endpoint)
    return endpoint


def delete(endpoint_id):
    delete_vm(endpoint_id)

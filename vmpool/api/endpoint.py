# coding: utf-8

import json

from flask import Blueprint, request, Response
from vmmaster.core.utils.utils import wait_for
from vmmaster.core.logger import log
from vmmaster.core.config import config

from vmpool.virtual_machines_pool import pool
from vmpool.platforms import Platforms
from vmpool.vmqueue import q

endpoint = Blueprint('endpoint', __name__)


def make_response(status=None, response=None):
    if not status:
        status = 500
    if not response:
        response = ''
    if isinstance(response, dict):
        response = json.dumps(response)

    return Response(status=status, response=response)


def give_vm(vm):
    return make_response(status=200, response=vm.info)


@endpoint.route('/<endpoint_id>', methods=['GET'])
def get_vm_from_pool(endpoint_id):
    vm = pool.get_by_id(endpoint_id)
    if vm:
        log.debug('Got vm for request with params: %s' % vm.info)
        return give_vm(vm)
    else:
        return make_response(status=404,
                             response='No such endpoint '
                                      'with id: %s' % endpoint_id)


@endpoint.route('/', methods=['POST'])
def new_vm():
    desired_caps = request.get_json()
    # TODO: fix avalanche logging by waiting sessions requests
    log.debug("Request with dc: %s" % str(desired_caps))
    platform = desired_caps.get('platform', None)

    if isinstance(platform, unicode):
        platform = platform.encode('utf-8')

    if not platform:
        return make_response(
            status=500,
            response='Platform for new endpoint not found')

    if not Platforms.check_platform(platform):
        return make_response(status=404,
                             response='No such platform %s' % platform)

    delayed_vm = q.enqueue(desired_caps)

    wait_for(lambda: delayed_vm.vm, timeout=config.GET_VM_TIMEOUT)

    if not delayed_vm.vm:
        delete_from_queue(delayed_vm)
        return make_response(
            status=500,
            response='Vm can\'t create with platform %s' % platform)

    wait_for(lambda: delayed_vm.vm.ready, timeout=config.GET_VM_TIMEOUT)

    if not delayed_vm.vm.ready:
        delete_from_queue(delayed_vm)
        return make_response(
            status=500,
            response='Vm has not been created with platform %s' % platform)

    log.info('Got vm for request with params: %s' % delayed_vm.vm.info)
    return give_vm(delayed_vm.vm)


@endpoint.route('/<endpoint_id>', methods=['DELETE'])
def delete_vm(endpoint_id):
    vm = pool.get_by_id(endpoint_id)
    if vm:
        if vm.is_preloaded():
            vm.rebuild()
        else:
            vm.delete()

        msg = "Vm with uuid %s has been deleted" % endpoint_id
        log.info(msg)
    else:
        msg = "Vm with uuid %s not found in pool or vm is busy" % endpoint_id
        log.info(msg)

    return make_response(status=200, response=msg)


def delete_from_queue(delayed_vm):
    log.info("Deleting request for getting vm from "
             "queue with desired capabilities: %s" % delayed_vm.dc)
    q.dequeue(delayed_vm)

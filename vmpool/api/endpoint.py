import json

from flask import Blueprint, request, Response
from vmmaster.core.utils.utils import wait_for
from vmmaster.core.logger import log
from vmmaster.core.config import config

from vmpool.virtual_machines_pool import pool
from vmpool.platforms import Platforms

endpoint = Blueprint('endpoint', __name__)


def make_response(status=None, response=None):
    if not status:
        status = 500
    if not response:
        response = ''
    if isinstance(response, dict):
        response = json.dumps(response)

    return Response(status=status, response=response)


@endpoint.route('/', methods=['POST'])
def get_vm():
    vm = None
    body = request.get_json()
    log.info("Request with dc: %s" % str(body))
    platform = body.get('platform', None)

    if isinstance(platform, unicode):
        platform = platform.encode('utf-8')

    if not platform:
        return make_response(
            status=500,
            response='Platform for new endpoint not found')

    if not Platforms.check_platform(platform):
        return make_response(status=404,
                             response='No such platform %s' % platform)

    if pool.has(platform):
        vm = pool.get(platform=platform)
    elif pool.can_produce(platform):
        vm = pool.add(platform)

    if vm is None:
        return make_response(
            status=500,
            response='Vm can\'t create with platform %s' % platform)

    wait_for(lambda: vm.ready is True, timeout=config.GET_VM_TIMEOUT)

    if not vm.ready:
        return make_response(
            status=500,
            response='Vm has not been created with platform %s' % platform)

    vm = {
        'id': vm.id,
        'platform': '%s' % vm.platform,
        'name': '%s' % vm.name,
        'ip': '%s' % vm.ip
    }
    log.info('Got vm for request with params: %s' % vm)
    return make_response(status=200, response=vm)


@endpoint.route('/<endpoint_id>', methods=['DELETE'])
def delete_vm(endpoint_id):
    vm = pool.get(_id=endpoint_id)
    if vm:
        if vm.name is not None and 'preloaded' in vm.name:
            vm.rebuild()
        else:
            vm.delete()

        msg = "Vm with uuid %s has been deleted" % endpoint_id
        log.info(msg)
    else:
        msg = "Vm with uuid %s not found in pool or vm is busy" % endpoint_id
        log.info(msg)

    return make_response(status=200, response=msg)

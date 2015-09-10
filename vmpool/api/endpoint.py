# coding: utf-8

from core.utils import wait_for
from core.logger import log
from core.config import config
from core.exceptions import PlatformException, NoSuchEndpoint, \
    CreationException

from vmpool.virtual_machines_pool import pool
from vmpool.platforms import Platforms
from vmpool.vmqueue import q


def get_vm_from_pool(endpoint_name):
    vm = pool.get_by_name(endpoint_name)
    if vm:
        log.debug('Got vm with params: %s' % vm.info)
        return vm
    else:
        raise NoSuchEndpoint('No such endpoint: %s' % endpoint_name)


def new_vm(desired_caps):
    platform = desired_caps.get('platform', None)

    if isinstance(platform, unicode):
        platform = platform.encode('utf-8')

    if not platform:
        return CreationException('Platform parameter for '
                                 'new endpoint not found in dc')

    if not Platforms.check_platform(platform):
        raise PlatformException('No such platform %s' % platform)

    delayed_vm = q.enqueue(desired_caps)

    wait_for(lambda: delayed_vm.vm, timeout=config.GET_VM_TIMEOUT)

    if not delayed_vm.vm:
        delete_from_queue(delayed_vm)
        raise CreationException('Сan\'t create vm with platform %s' % platform)

    wait_for(lambda: delayed_vm.vm.ready, timeout=config.GET_VM_TIMEOUT)

    if not delayed_vm.vm.ready:
        delete_from_queue(delayed_vm)
        raise CreationException(
            'Timeout while building vm %s (platform: %s)' %
            (delayed_vm.vm.id, platform)
        )

    log.info('Got vm for request with params: %s' % delayed_vm.vm.info)
    return delayed_vm.vm.info


def delete_vm(endpoint_name):
    vm = pool.get_by_name(endpoint_name)
    if vm:
        if vm.is_preloaded():
            vm.rebuild()
        else:
            vm.delete()

        msg = "Vm %s has been deleted" % endpoint_name
        log.info(msg)
    else:
        msg = "Vm %s not found in pool or vm is busy" % endpoint_name
        log.info(msg)


def delete_from_queue(delayed_vm):
    log.info("Deleting request for getting vm from "
             "queue with desired capabilities: %s" % delayed_vm.dc)
    q.dequeue(delayed_vm)

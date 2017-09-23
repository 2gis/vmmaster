# coding: utf-8

import time
import logging

from core.utils import generator_wait_for
from core.config import config
from core.profiler import profiler

from core.exceptions import PlatformException, CreationException

from flask import current_app

log = logging.getLogger(__name__)


def get_vm(platform):
    timer = profiler.functions_duration_manual(get_vm.__name__)

    if not current_app.pool.check_platform(platform):
        raise PlatformException('No platforms {} found in pool: {})'.format(
            platform, current_app.pool.platforms.info())
        )

    vm = None
    sleep_time, sleep_time_increment = 0.5, 0.5
    for _ in generator_wait_for(
        lambda: vm, timeout=config.GET_VM_TIMEOUT
    ):
        vm = current_app.pool.get_vm(platform)
        if vm:
            break
        else:
            sleep_time += sleep_time_increment
            log.debug("Waiting {} seconds before next attempt to get endpoint".format(sleep_time))
            time.sleep(sleep_time)
    else:
        raise CreationException(
            "Timeout while waiting for vm with platform %s" % platform
        )

    for _ in generator_wait_for(
        lambda: vm.ready, timeout=config.GET_VM_TIMEOUT
    ):
        if vm.ready:
            break
    else:
        vm.delete()
        raise CreationException(
            'Timeout while building vm %s (platform: %s)' %
            (vm.name, platform)
        )

    log.info('Got vm for request with params: %s' % vm.info)
    timer.end()
    yield vm

# coding: utf-8
import time
import logging

from core.utils import generator_wait_for
from core.config import config
from core.profiler import profiler

from core.exceptions import PlatformException, CreationException

from flask import current_app

log = logging.getLogger(__name__)


def get_platform(desired_caps):
    if hasattr(config, 'PLATFORM'):
        log.info('Using {}. Desired platform {} has been ignored.'.format(
            config.PLATFORM, desired_caps.get('platform'))
        )
        platform = config.PLATFORM
        desired_caps['platform'] = platform

    matched_platforms = current_app.pool.get_matched_platforms(desired_caps)
    for platform in matched_platforms:
        if current_app.pool.check_platform(platform):
            return platform
    else:
        raise PlatformException('No platforms {} found in pool: {})'.format(
            matched_platforms, current_app.pool.platforms.info())
        )


def get_vm(desired_caps):
    timer = profiler.functions_duration_manual(get_vm.__name__)
    platform = get_platform(desired_caps)

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

    if not vm:
        raise CreationException(
            "Timeout while waiting for vm with platform %s" % platform
        )

    for _ in generator_wait_for(
        lambda: vm.ready, timeout=config.GET_VM_TIMEOUT
    ):
        if vm.ready:
            break

    if not vm.ready:
        vm.delete(try_to_rebuild=False)
        raise CreationException(
            'Timeout while building vm %s (platform: %s)' %
            (vm.name, platform)
        )

    log.info('Got vm for request with params: %s' % vm.info)
    timer.end()
    yield vm

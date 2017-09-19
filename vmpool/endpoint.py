# coding: utf-8
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

    matched_platforms = current_app.matcher.get_matched_platforms(desired_caps)
    for platform in matched_platforms:
        if current_app.pool.platforms.check_platform(platform):
            return platform
    else:
        raise PlatformException('No platforms {} found in pool: {})'.format(
            matched_platforms, current_app.pool.platforms.info())
        )


def get_vm(desired_caps):
    timer = profiler.functions_duration_manual(get_vm.__name__)
    platform = get_platform(desired_caps)

    vm = None
    for _ in generator_wait_for(
        lambda: vm, timeout=config.GET_VM_TIMEOUT
    ):
        vm = current_app.pool.get_vm(platform)
        yield vm
        if vm:
            break
    else:
        raise CreationException(
            "Timeout while waiting for vm with platform %s" % platform
        )

    yield vm

    for _ in generator_wait_for(
        lambda: vm.ready, timeout=config.GET_VM_TIMEOUT
    ):
        yield vm
        if vm.ready:
            break
    else:
        vm.delete(try_to_rebuild=False)
        raise CreationException(
            'Timeout while building vm %s (platform: %s)' %
            (vm.name, platform)
        )

    log.info('Got vm for request with params: %s' % vm.info)
    timer.end()
    yield vm

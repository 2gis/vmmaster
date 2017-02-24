# coding: utf-8
import logging

import time
import json

from core import constants
from core.utils import generator_wait_for
from core.config import config

from core.exceptions import PlatformException, CreationException

from flask import current_app

log = logging.getLogger(__name__)


def get_platform(desired_caps):
    platform = desired_caps.get('platform', None)

    if hasattr(config, "PLATFORM") and config.PLATFORM:
        log.info(
            'Using %s. Desired platform %s has been ignored.' %
            (config.PLATFORM, platform)
        )
        platform = config.PLATFORM
        desired_caps["platform"] = platform

    if isinstance(platform, unicode):
        platform = platform.encode('utf-8')

    if not platform:
        raise PlatformException(
            'Platform parameter for new endpoint not found in dc'
        )

    # if not current_app.pool.platforms.check_platform(platform):
    #     raise PlatformException('No such platform %s' % platform)

    return platform


def get_vm(desired_caps):
    platform = get_platform(desired_caps)

    vm = None
    for _ in generator_wait_for(
        lambda: vm, timeout=config.GET_VM_TIMEOUT
    ):
        vm = current_app.pool.get_vm(platform)
        if vm:
            break

    if not vm:
        raise CreationException(
            "Timeout while waiting for vm with platform %s" % platform
        )

    for _ in generator_wait_for(
        lambda: vm, timeout=config.GET_VM_TIMEOUT
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
    yield vm


def get_endpoint(session_id, dc):
    _endpoint = None
    attempt = 0
    attempts = getattr(config, "GET_ENDPOINT_ATTEMPTS",
                       constants.GET_ENDPOINT_ATTEMPTS)
    wait_time = 0
    wait_time_increment = getattr(config, "GET_ENDPOINT_WAIT_TIME_INCREMENT",
                                  constants.GET_ENDPOINT_WAIT_TIME_INCREMENT)

    dc = json.loads(dc)
    while not _endpoint:
        attempt += 1
        wait_time += wait_time_increment
        try:
            log.info("Try to get endpoint for session %s. Attempt %s" % (session_id, attempt))
            for vm in get_vm(dc):
                _endpoint = vm
                yield _endpoint
            if attempt < attempts:
                time.sleep(wait_time)
            log.info("Attempt %s to get endpoint %s for session %s was succeed"
                     % (attempt, _endpoint, session_id))
        except CreationException as e:
            log.exception("Attempt %s to get endpoint for session %s was failed: %s"
                          % (attempt, session_id, str(e)))
            if hasattr(_endpoint, "ready"):
                if not _endpoint.ready:
                    _endpoint = None
            if attempt > attempts:
                raise e

    yield _endpoint

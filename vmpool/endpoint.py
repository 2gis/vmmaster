# coding: utf-8

import time
import logging
from threading import Thread, Lock

from core import constants
from core.utils import generator_wait_for, call_in_thread
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


class EndpointRemover(Thread):
    def __init__(self, platforms, artifact_collector, database, app_context):
        super(EndpointRemover, self).__init__()
        self.running = True
        self.daemon = True
        self.platforms = platforms
        self.artifact_collector = artifact_collector
        self.database = database
        self.app_context = app_context
        self.lock = Lock()

    @call_in_thread
    def remove_endpoint(self, endpoint, try_to_rebuild=False):
        try:
            with self.app_context():
                self.endpoint_service_mode_on(endpoint)
                session = self.database.get_session_by_endpoint_id(endpoint.id)
                if session:
                    session.restore()
                    self.artifact_collector.save_selenium_log(session)
                    self.artifact_collector.wait_for_complete(session)
                endpoint.delete(try_to_rebuild=try_to_rebuild)
                self.endpoint_service_mode_off(endpoint)
        except:
            log.exception("Attempt to remove {} was failed".format(endpoint))
            endpoint.send_to_service()

    def endpoint_service_mode_on(self, endpoint):
        with self.lock:
            endpoint.service_mode_on()

    def endpoint_service_mode_off(self, endpoint):
        with self.lock:
            endpoint.service_mode_off()

    def run(self):
        log.info("EndpointRemover was started...")
        while self.running:
            for endpoint in self.platforms.wait_for_service:
                self.remove_endpoint(endpoint, try_to_rebuild=True)
            time.sleep(constants.ER_SLEEP_TIME)

    def remove_all(self):
        log.info("Deleting endpoints: {}".format(self.platforms.active_endpoints))
        with self.app_context():
            for endpoint in self.platforms.active_endpoints:
                endpoint.delete(try_to_rebuild=False)

    def stop(self):
        self.running = False
        try:
            self.remove_all()
        finally:
            self.join(1)
            log.info("EndpointRemover was stopped")

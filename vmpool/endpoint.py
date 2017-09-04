# coding: utf-8

import time
import logging
from threading import Thread

from core import constants
from core.utils import generator_wait_for
from core.config import config
from core.profiler import profiler

from core.exceptions import PlatformException, CreationException

from flask import current_app
from vmpool.artifact_collector import ArtifactCollector, screencast_recording

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


def get_endpoint(session_id, dc):
    _endpoint = None
    attempt = 0
    attempts = getattr(config, "GET_ENDPOINT_ATTEMPTS",
                       constants.GET_ENDPOINT_ATTEMPTS)
    wait_time = 0
    wait_time_increment = getattr(config, "GET_ENDPOINT_WAIT_TIME_INCREMENT",
                                  constants.GET_ENDPOINT_WAIT_TIME_INCREMENT)

    while not _endpoint:
        attempt += 1
        wait_time += wait_time_increment
        try:
            log.info("Try to get endpoint for session %s. Attempt %s" % (session_id, attempt))
            for vm in get_vm(dc):
                _endpoint = vm
                yield _endpoint
            profiler.register_success_get_endpoint(attempt)
            log.info("Attempt %s to get endpoint %s for session %s was succeed"
                     % (attempt, _endpoint, session_id))
        except CreationException as e:
            log.exception("Attempt %s to get endpoint for session %s was failed: %s"
                          % (attempt, session_id, str(e)))
            if _endpoint and not _endpoint.ready:
                _endpoint.delete()
                _endpoint = None
            if attempt < attempts:
                time.sleep(wait_time)
            else:
                profiler.register_fail_get_endpoint()
                raise e

    yield _endpoint


def prepare_endpoint(app, session_id, queue):
    with app.app_context():
        session = app.sessions.get_session(session_id)
        try:
            for _endpoint in get_endpoint(session.id, session.dc):
                session.endpoint_id = _endpoint.id
                session.save()
                log.info("Founded endpoint({}) session {}".format(session.endpoint_id, session))
                queue.add_task(
                    session.id,
                    screencast_recording,
                    *(app, session.id)
                )
        except:
            session.set_status("waiting")


class EndpointWorker(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.app = pool.app
        self.sessions = pool.app.sessions
        self.platforms = pool.platforms
        self.queue = ArtifactCollector()

    def run(self):
        log.info("EndpointWorker starting...")
        while self.running:
            with self.app.app_context():
                for session in self.sessions.active():
                    if session.status == "waiting" \
                            and self.platforms.check_platform(session.platform) \
                            and session.id not in self.queue.in_queue.keys():
                            log.info("Finding for {}".format(session))
                            session.set_status("preparing")
                            self.queue.add_task(
                                session.id,
                                prepare_endpoint,
                                *(self.app, session.id, self.queue)
                            )
                time.sleep(5)

    def stop(self):
        self.running = False
        self.join(1)
        log.info("EndpointWorker stopped")

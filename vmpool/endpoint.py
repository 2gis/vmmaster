# coding: utf-8
import logging

import time
import json
from threading import Thread
from multiprocessing.pool import ThreadPool

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


def on_completed_task(session_id):
    """
    :param session_id: int
    """
    log.debug("Completing task for session %s" % session_id)
    session = get_session_from_db(session_id)

    if not session:
        log.error("Task doesn't sucessfully finished for session %s "
                  "and endpoint doesn't deleted" % session_id)
        return

    log.debug("Task finished for session %s" % session_id)


def get_session_from_db(session_id):
    """
    :param session_id: int
    :return: Session
    """
    session = None
    try:
        session = current_app.database.get_session(session_id)
    except:
        log.exception("Session %s not found" % session_id)

    return session


class EndpointThreadPool(ThreadPool):
    def __init__(self, vmpool):
        super(EndpointThreadPool, self).__init__(processes=config.ENDPOINT_THREADPOOL_PROCESSES)
        self.in_queue = {}
        self.vmpool = vmpool
        log.info("EndpointThreadPool started")

    def __reduce__(self):
        super(EndpointThreadPool, self).__reduce__()

    def get_queue(self):
        return self.in_queue.keys()

    def add_task(self, session_id):
        self.run_task(
            session_id,
            self.prepare_endpoint,
            args=(session_id,)
        )
        return True

    def run_task(self, session_id, method, args):
        apply_result = self.apply_async(method, args=args)
        log.debug("Apply Result %s" % apply_result)
        if session_id in self.in_queue:
            self.in_queue[session_id].append(apply_result)
        else:
            self.in_queue[session_id] = [apply_result]
        log.info("Task for getting artifacts added to queue for session %s" % session_id)
        log.debug('ArtifactCollector Queue: %s' % str(self.in_queue))

    def del_task(self, session_id):
        """
        :param session_id: int
        """
        tasks = self.in_queue.get(session_id, list())
        for task in tasks:
            if task and not task.ready():
                task.successful()
                log.info("Getting artifacts for session %s aborted" % session_id)
        try:
            del self.in_queue[session_id]
        except KeyError:
            log.exception("Tasks already deleted from queue for session %s" % session_id)
        log.info("Getting artifacts abort has been failed for "
                 "session %s because it's already done" % session_id)

    def del_tasks(self, sessions_ids):
        """
        :param sessions_ids: list
        """
        for session_id in sessions_ids:
            self.del_task(session_id)

    def prepare_endpoint(self, session_id):
        with self.vmpool.app.app_context():
            session = get_session_from_db(session_id=session_id)
            try:
                for _endpoint in get_endpoint(session.id, session.dc):
                    log.info("Endpoint %s" % _endpoint)
                    session.set_endpoint(_endpoint)
                    log.info("Endpoint id: %s" % str(session.endpoint.id))
            finally:
                self.in_queue.pop(session.id)
                on_completed_task(session.id)

    def stop(self):
        self.del_tasks(self.in_queue.keys())
        self.close()
        log.info("EndpointThreadPool stopped")


class EndpointWorker(Thread):
    def __init__(self, pool):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.app = pool.app
        self.sessions = pool.app.sessions
        self.platforms = pool.platforms
        self.queue = EndpointThreadPool(pool)

    def run(self):
        log.info("EndpointWorker starting")
        with self.app.app_context():
            while self.running:
                for session in self.sessions.active():
                    log.info("Checking for %s" % session)
                    if not session.endpoint_id and not session.closed:
                        if self.platforms.check_platform(session.platform):
                            in_queue = self.queue.add_task(session.id)
                            if in_queue:
                                log.info("Added to queue for preparing endpoint "
                                         "for %s with platform=%s" % (session, session.platform))
                            else:
                                log.warn("Not in queue task for session %s" % session)
                time.sleep(5)

    def stop(self):
        self.running = False
        self.join(1)
        log.info("EndpointWorker stopped")

# coding: utf-8

import time
import logging
from threading import Thread

from core import constants
from core.exceptions import CreationException, EndpointUnreachableError, AddTaskException
from core.utils import call_in_thread
from core.profiler import profiler

log = logging.getLogger(__name__)


class EndpointRemover(Thread):
    def __init__(self, platforms, artifact_collector, database, app_context):
        super(EndpointRemover, self).__init__()
        self.running = True
        self.daemon = True
        self.platforms = platforms
        self.artifact_collector = artifact_collector
        self.database = database
        self.app_context = app_context

    @call_in_thread
    def remove_endpoint(self, endpoint, try_to_rebuild=False):
        with self.app_context():
            try:
                endpoint.service_mode_on()
                session = self.database.get_session_by_endpoint_id(endpoint.id)
                if session:
                    self.artifact_collector.save_selenium_log(session)
                    self.artifact_collector.wait_for_complete(session.id)
                endpoint.delete(try_to_rebuild=try_to_rebuild)
                endpoint.service_mode_off()
            except AddTaskException:
                endpoint.delete(try_to_rebuild=False)
                endpoint.service_mode_off()
            except:
                log.exception("Attempt to remove {} was failed".format(endpoint))
                endpoint.send_to_service()

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


class EndpointPreparer(Thread):
    def __init__(self, pool, sessions, artifact_collector, app_context):
        Thread.__init__(self)
        self.running = True
        self.daemon = True
        self.pool = pool
        self.app_context = app_context
        self.sessions = sessions
        self.artifact_collector = artifact_collector
        self.provider_id = pool.provider.id

    @call_in_thread
    def prepare_endpoint(self, session, get_endpoint_attempts=constants.GET_ENDPOINT_ATTEMPTS):
        with self.app_context():
            session.set_status("preparing")

            attempt, wait_time = 0, 2
            while self.running:
                attempt += 1
                wait_time *= 2

                session.refresh()
                if session.closed:
                    log.warning("Attempt {} was aborted because session {} was closed".format(attempt, session.id))
                    break

                if session.endpoint:
                    log.warning("Attempt {} was aborted because session {} already have endpoint_id".format(
                        attempt, session.id, session.endpoint_id)
                    )
                    break

                log.info("Try to find endpoint {} for {}. Attempt {}".format(session.platform, session, attempt))
                try:
                    _endpoint = self.pool.get_vm(session.platform, session.dc)
                    if not self.running:
                        if _endpoint:
                            _endpoint.delete()
                        break

                    if self.running and _endpoint:
                        profiler.register_success_get_endpoint(attempt)
                        session.set_endpoint(_endpoint)
                        log.info("Attempt {} to find endpoint {} for session {} was succeed".format(
                            attempt, session.platform, session)
                        )
                        break

                    if _endpoint and getattr(_endpoint, "ready", False):
                        raise CreationException("Got non-ready endpoint or None: {}".format(_endpoint))
                    else:
                        raise EndpointUnreachableError("Endpoint wasn't returned, was returned None")
                except EndpointUnreachableError as e:
                    log.debug("Attempt {} to get endpoint for session {} was failed: {}".format(
                        attempt, session.id, e.message)
                    )
                except:
                    log.exception("Attempt {} to get endpoint for session {} was failed".format(
                        attempt, session.id)
                    )

                if attempt < get_endpoint_attempts:
                    log.debug("Waiting {} seconds before next attempt {} to get endpoint".format(
                        wait_time, attempt + 1)
                    )
                    time.sleep(wait_time)
                else:
                    profiler.register_fail_get_endpoint()
                    break

            session.refresh()
            if not session.endpoint_id and session.is_preparing:
                session.set_status("waiting")

    def start_screencast(self, session):
        session.set_screencast_started(True)
        self.artifact_collector.record_screencast(session)

    def _run_tasks(self):
        with self.app_context():
            for session in self.sessions.active(provider_id=self.provider_id):
                session.refresh()
                if session.is_running and not session.screencast_started and session.take_screencast:
                    self.start_screencast(session)
                elif session.is_waiting:
                    if not self.pool.check_platform(session.platform):
                        continue

                    if not self.pool.has(session.platform) and not self.pool.can_produce(session.platform):
                        continue

                    self.prepare_endpoint(session)

    def run(self):
        log.info("EndpointPreparer starting...")
        while self.running:
            self._run_tasks()
            time.sleep(constants.EP_SLEEP_TIME)

    def stop(self):
        self.running = False
        self.join(1)
        log.info("EndpointPreparer was stopped")

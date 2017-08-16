# coding: utf-8
import time
from prometheus_client import Counter, Gauge


class Profiler(object):
    METRICS_NAMESPACE = "vmmaster"

    def __init__(self):
        self._requests_duration_seconds = Gauge(
            "requests_duration_seconds",
            "Request duration (seconds)",
            labelnames=["command"],
            namespace=self.METRICS_NAMESPACE
        )
        self._get_session_total = Counter(
            "get_session_total",
            "Amount of get session requests",
            namespace=self.METRICS_NAMESPACE
        )
        self._get_endpoint_total = Counter(
            "get_endpoint_total",
            "Amount of processed get_endpoint",
            labelnames=["status"],
            namespace=self.METRICS_NAMESPACE
        )
        self._get_endpoint_attempts_total = Gauge(
            "get_endpoint_attempts_total",
            "Number of attempts before success get endpoint",
            namespace=self.METRICS_NAMESPACE
        )
        self._functions_duration_seconds = Gauge(
            "functions_duration_seconds",
            "Function duration (seconds)",
            labelnames=["name"],
            namespace=self.METRICS_NAMESPACE
        )

    def requests_duration(self, command):
        """
        Time a block of code or function, and set the duration in seconds.
        Can be used as a function decorator or context manager.
        """
        return self._requests_duration_seconds.labels(command=command).time()

    def register_get_session_call(self):
        self._get_session_total.inc()

    def register_success_get_endpoint(self, attempt):
        self._get_endpoint_total.labels(status="success").inc()
        self._get_endpoint_attempts_total.set(attempt)

    def register_fail_get_endpoint(self):
        self._get_endpoint_total.labels(status="fail").inc()

    def functions_duration_manual(self, name):
        """
        Start and return timer with 'end()' function for manually call
        """
        return _GaugeTimer(self._functions_duration_seconds, name=name)


profiler = Profiler()


class _GaugeTimer(object):
    def __init__(self, gauge, **labels):
        self.start_time = time.time()
        self._gauge = gauge
        self._labels = labels

    def end(self):
        self._gauge.labels(**self._labels).set(time.time() - self.start_time)

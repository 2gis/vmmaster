# coding: utf-8
import time


class TimeoutException(Exception):
    pass


def wait_for(condition, timeout=5):
    start = time.time()
    while not condition() and time.time() - start < timeout:
        time.sleep(0.1)

    return condition()
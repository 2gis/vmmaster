# coding: utf-8

import logging

log = logging.getLogger(__name__)


ROUTES = [
    ("GET", "/", "dashboard")
]


def dashboard(request):
    return "Hi, bro!"

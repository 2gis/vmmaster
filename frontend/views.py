# coding: utf-8

import logging
from frontend import app

log = logging.getLogger(__name__)


@app.register("/", "/dashboard")
def dashboard(request):
    return "Hello, my daddy!"

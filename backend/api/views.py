# coding: utf-8
import logging
from backend import app


BASE_URL = '/api'
log = logging.getLogger(__name__)


@app.register("%s/sessions" % BASE_URL, methods=["GET"])
async def sessions(request):
    return request.app.sessions


@app.register("%s/messages" % BASE_URL, methods=["GET"])
async def messages(request):
    return request.app.queue_producer.messages

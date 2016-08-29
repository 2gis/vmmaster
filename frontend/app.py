# coding: utf-8

import logging
from uuid import uuid1
from muffin import Application


log = logging.getLogger(__name__)


class FrontendApp(Application):
    def __init__(self, *args, **kwargs):
        super(FrontendApp, self).__init__(*args, **kwargs)
        self.uuid = str(uuid1())


def create_app():
    return FrontendApp(
        'frontend',
        CONFIG='frontend.config.debug'
    )

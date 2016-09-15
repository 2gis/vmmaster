# coding: utf-8

import logging
from uuid import uuid1
from core import common


log = logging.getLogger(__name__)


class FrontendApp(common.BaseApplication):
    def __init__(self, *args, **kwargs):
        super(FrontendApp, self).__init__(*args, **kwargs)
        self.uuid = str(uuid1())


def create_app():
    return FrontendApp(
        'frontend',
        CONFIG='config.debug'
    )

# coding: utf-8

import os
import logging
import logging.config
from uuid import uuid4
from aiohttp import web
from importlib import import_module
from cached_property import cached_property

from core import utils


log = logging.getLogger(__name__)


class BaseApplication(web.Application):
    # Default application settings
    defaults = {
        # Path to configuration module
        'CONFIG': None,

        # Enable debug mode
        'DEBUG': False,

        # Default encoding
        'ENCODING': 'utf-8',

        # Default logging
        'LOG_LEVEL': 'WARNING',
        'LOG_FORMAT': '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
        'LOG_DATE_FORMAT': '[%Y-%m-%d %H:%M:%S %z]'
    }

    def __init__(self, name, loop=None, router=None, middlewares=(), **OPTIONS):
        super().__init__(loop=loop, router=router, middlewares=middlewares)
        self.uuid = str(uuid4())[:8]
        self.name = "%s_%s" % (name, self.uuid)
        self.setup_app(**OPTIONS)

    def copy(self):
        log.debug("Method not implemented")

    def setup_app(self, **OPTIONS):
        # Overide options
        self.defaults['CONFIG'] = OPTIONS.pop('CONFIG', self.defaults['CONFIG'])
        self.cfg.update(OPTIONS)
        self._debug = self.cfg.DEBUG

        # Setup logging
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(self.cfg.LOG_FORMAT, self.cfg.LOG_DATE_FORMAT))
        self.logger.addHandler(ch)
        self.logger.setLevel(self.cfg.LOG_LEVEL)
        self.logger.name = 'backend'
        self.logger.propagate = False

        LOGGING_CFG = self.cfg.get('LOGGING')
        if LOGGING_CFG and isinstance(LOGGING_CFG, dict):
            logging.config.dictConfig(LOGGING_CFG)

    @cached_property
    def cfg(self):
        """Load the application configuration.

        This method loads configuration from python module.
        """
        config = utils.LStruct(self.defaults)
        module = config['CONFIG'] = os.environ.get(
            "CONFIG", config['CONFIG'])

        if module:
            try:
                module = import_module(module)
                config.update({
                    name: getattr(module, name) for name in dir(module)
                    if name == name.upper() and not name.startswith('_')
                })

            except ImportError as exc:
                config.CONFIG = None
                print("Error importing %s: %s" % (module, exc))

        return config

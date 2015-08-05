# coding: utf-8

from flask import Flask
from platforms import Platforms
from vmpool.vmqueue import q, QueueWorker
from vmpool.virtual_machines_pool import pool
from vmpool.virtual_machines_pool import VirtualMachinesPoolPreloader, \
    VirtualMachineChecker
from vmmaster.core.logger import log, setup_logging
from vmmaster.core.config import setup_config, config
from vmmaster.core.utils.init import home_dir
from api.endpoint import endpoint
from api.api import api

if not config:
    setup_config('%s/config.py' % home_dir())
setup_logging(logdir=config.LOG_DIR, logfile_name='vmpool.log')


class VMPoolApplication(Flask):
    def __init__(self, *args, **kwargs):
        super(VMPoolApplication, self).__init__(*args, **kwargs)
        log.info('Running application...')
        self.platforms = Platforms()
        self.queue = q

        self.preloader = VirtualMachinesPoolPreloader(pool)
        self.preloader.start()
        self.vmchecker = VirtualMachineChecker(pool)
        self.vmchecker.start()
        self.worker = QueueWorker(self.queue)
        self.worker.start()

    def shutdown(self):
        log.info("Shutting down...")
        self.worker.stop()
        self.preloader.stop()
        self.vmchecker.stop()
        pool.free()
        log.info("VM Pool gracefully shut down.")


def app():
    poolapp = VMPoolApplication(__name__)
    poolapp.register_blueprint(endpoint, url_prefix='/endpoint')
    poolapp.register_blueprint(api, url_prefix='/api')
    return poolapp

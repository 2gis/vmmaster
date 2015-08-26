import logging
import logging.handlers
import graypy
import os
import sys

from .config import config


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


def setup_logging(logdir=None, logfile_name='vmmaster.log', scrnlog=True, txtlog=True, loglevel=None):
    if loglevel is None:
        loglevel = logging.getLevelName(config.LOG_LEVEL.upper())

    logdir = os.path.abspath(logdir)

    if not os.path.exists(logdir):
        os.mkdir(logdir)

    log = logging.getLogger('')
    log.setLevel(loglevel)

    log_formatter = logging.Formatter("%(asctime)s - %(levelname)-7s :: %(name)-6s :: %(message)s")

    if txtlog:
        txt_handler = logging.handlers.RotatingFileHandler(
            os.path.join(logdir, logfile_name), maxBytes=config.LOG_SIZE, backupCount=5
        )
        txt_handler.setFormatter(log_formatter)
        log.addHandler(txt_handler)
        
        log.info("Logger initialised.")

    if scrnlog:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        log.addHandler(console_handler)

    if config.LOG_LEVEL.lower():
        stdout_logger = logging.getLogger('STDOUT')
        slout = StreamToLogger(stdout_logger, logging.INFO)
        sys.stdout = slout

    if hasattr(config, 'GRAYLOG'):
        from core.utils.network_utils import ping

        host =config.GRAYLOG[0]
        port = config.GRAYLOG[1]

        if ping(host, port):
            graylog_handler = graypy.GELFHandler(host=host, port=port)
            graylog_handler.setFormatter(log_formatter)
            log.addHandler(graylog_handler)
        else:
            log.info('GRAYLOG URL not available')

    stderr_logger = logging.getLogger('STDERR')
    slerr = StreamToLogger(stderr_logger, logging.ERROR)
    sys.stderr = slerr

    return log


log = logging.getLogger('LOG')
log_cleanup = logging.getLogger('cleanup')
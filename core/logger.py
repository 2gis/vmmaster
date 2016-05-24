import os
import sys
import json
import graypy
import socket
import logging
import traceback
import logging.handlers

from config import config
from datetime import datetime
from core.utils.network_utils import ping


class LogstashFormatter(logging.Formatter):

    def __init__(self, message_type=None, tags=None, fqdn=False):
        self.message_type = message_type if message_type else "vmmaster"
        self.tags = tags if tags is not None else []

        if fqdn:
            self.host = socket.getfqdn()
        else:
            self.host = socket.gethostname()

    def get_extra_fields(self, record):
        # The list contains all the attributes listed in
        # http://docs.python.org/library/logging.html#logrecord-attributes
        skip_list = (
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'extra')

        if sys.version_info < (3, 0):
            easy_types = (basestring, bool, dict, float, int, long, list, type(None))
        else:
            easy_types = (str, bool, dict, float, int, list, type(None))

        fields = {}

        for key, value in record.__dict__.items():
            if key not in skip_list:
                if isinstance(value, easy_types):
                    fields[key] = value
                else:
                    fields[key] = repr(value)

        return fields

    def get_debug_fields(self, record):
        fields = {
            'stack_trace': self.format_exception(record.exc_info),
            'lineno': record.lineno,
            'process': record.process,
            'thread_name': record.threadName,
        }

        if not getattr(record, 'funcName', None):
            fields['funcName'] = record.funcName

        if not getattr(record, 'processName', None):
            fields['processName'] = record.processName

        return fields

    @classmethod
    def format_source(cls, message_type, host, path):
        return "%s://%s/%s" % (message_type, host, path)

    @classmethod
    def format_timestamp(cls, time):
        tstamp = datetime.utcfromtimestamp(time)
        return tstamp.strftime("%Y-%m-%dT%H:%M:%S") + ".%03d" % (tstamp.microsecond / 1000) + "Z"

    @classmethod
    def format_exception(cls, exc_info):
        return ''.join(traceback.format_exception(*exc_info)) if exc_info else ''

    @classmethod
    def serialize(cls, message):
        if sys.version_info < (3, 0):
            return json.dumps(message)
        else:
            return bytes(json.dumps(message), 'utf-8')

    def format(self, record):
        message = {
            '@timestamp': self.format_timestamp(record.created),
            '@version': '1',
            'message': record.getMessage(),
            'host': self.host,
            'path': record.pathname,
            'tags': self.tags,
            'type': self.message_type,

            # Extra Fields
            'level': record.levelname,
            'logger_name': record.name,
        }

        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        if record.exc_info:
            message.update(self.get_debug_fields(record))

        return self.serialize(message)


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


def add_screen_handler(log, log_formatter):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    log.addHandler(console_handler)


def add_text_handler(log, log_formatter, logdir, logfile_name):
    txt_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logdir, logfile_name),
        maxBytes=config.LOG_SIZE,
        backupCount=5
    )
    txt_handler.setFormatter(log_formatter)
    log.addHandler(txt_handler)
    log.info("Logger initialised.")


def add_graylog_handler(log, log_formatter):
    host, port = config.GRAYLOG

    if ping(host, port):
        graylog_handler = graypy.GELFHandler(host=host, port=port)
        graylog_handler.setFormatter(log_formatter)
        log.addHandler(graylog_handler)
        log.info("GRAYLOG Handler initialised.")
    else:
        log.warn('GRAYLOG URL not available')


def setup_logging(logname='', logdir=None, logfile_name='vmmaster.log',
                  scrnlog=True, txtlog=True, loglevel=None,
                  message_type="vmmaster", tags=None, fqdn=False):
    if not loglevel:
        loglevel = logging.getLevelName(config.LOG_LEVEL.upper())

    logdir = os.path.abspath(logdir)

    if not os.path.exists(logdir):
        os.mkdir(logdir)

    log = logging.getLogger(logname)
    log.setLevel(loglevel)

    if hasattr(config, "LOG_FORMAT") and config.LOG_FORMAT == 'json':
        log_formatter = LogstashFormatter(
            message_type=message_type, tags=tags, fqdn=fqdn
        )
    else:
        log_format = \
            "%(asctime)s - %(levelname)-7s :: %(name)-6s :: %(message)s" \
            if scrnlog else "%(asctime)s - %(levelname)-7s :: %(message)s"
        log_formatter = logging.Formatter(log_format)

    if scrnlog:
        add_screen_handler(log, log_formatter)

    if txtlog:
        add_text_handler(log, log_formatter, logdir, logfile_name)

    if hasattr(config, 'GRAYLOG'):
        add_graylog_handler(log, log_formatter)

    stdout_logger = logging.getLogger('STDOUT')
    sys.stdout = StreamToLogger(stdout_logger, loglevel)

    stderr_logger = logging.getLogger('STDERR')
    sys.stderr = StreamToLogger(stderr_logger, logging.ERROR)

    return log


log = logging.getLogger('LOG')
log_pool = logging.getLogger('POOL')

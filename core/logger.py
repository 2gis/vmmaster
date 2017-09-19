import os
import sys
import json
import socket
import traceback
import logging
import logging.config
import logging.handlers
from datetime import datetime
log = logging.getLogger(__name__)

logging.getLogger("envparse").setLevel(logging.WARNING)
logging.getLogger("docker").setLevel(logging.WARNING)


class LogstashFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None, message_type=None, tags=None, fqdn=False):
        super(LogstashFormatter, self).__init__(fmt=fmt, datefmt=datefmt)
        self.message_type = message_type if message_type else "vmmaster"
        self.tags = tags if tags is not None else []
        self.team = "vmmaster"
        self.project = "vmmaster"

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
            'team': self.team,
            'project': self.project,

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

    def __init__(self, logger, log_level=logging.ERROR):
        self.logger = logger
        self.log_level = log_level
        self.message = ''

    def __del__(self):
        if self.message:
            self.logger.error(self.message)

    def flush(self):
        pass

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.message += "\n%s" % line


def set_loggers(log_type, log_level):
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                'format': '%(asctime)s - %(levelname)-7s :: %(name)-6s :: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        "handlers": {
            "default": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "standard"
            }
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": log_level,
                'propagate': True
            }
        }
    }
    if log_type == "logstash":
        logging_config["formatters"]["standard"] = {
            "()": "core.logger.LogstashFormatter"
        }

    return logging_config


def setup_logging(log_type=None, log_level=None):
    log_level = log_level if log_level else logging.getLevelName(logging.INFO)

    if os.path.exists("logging.ini"):
        logging.config.fileConfig(
            "logging.ini", disable_existing_loggers=False
        )
        log.warning("logger from logging.ini initialised.")
    elif log_type:
        config = set_loggers(log_type, log_level)
        logging.config.dictConfig(config)
        log.info("%s logger initialised." % log_type)

# @TODO fix me. log does stop writing after uncommenting this.
# sys.stderr = StreamToLogger(logging.getLogger('STDERR'))
# sys.stdout = StreamToLogger(logging.getLogger('STDOUT'))

import logging
import logging.config
import logging.handlers
from os.path import isfile
from envparse import env
from core.logger import setup_logging

log = logging.getLogger(__name__)
if isfile('.env'):
    log.warning("Setting variables from .env file")
    env.read_envfile('.env')
else:
    log.warning(".env file was not found")

DEBUG = env.bool("DEBUG", default=False)

# logging
LOG_TYPE = env.str("LOG_TYPE", default="plain")
LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")
LOGGING = setup_logging(log_type=LOG_TYPE, log_level=LOG_LEVEL)

RABBITMQ_USER = env.str("RABBITMQ_USER", default="user")
RABBITMQ_PASSWORD = env.str("RABBITMQ_PASSWORD", default="pass")
RABBITMQ_HOST = env.str("RABBITMQ_HOST", default="host")
RABBITMQ_PORT = env.int("RABBITMQ_PORT", default=5672)
RABBITMQ_COMMAND_QUEUE = env.str("RABBITMQ_COMMAND_QUEUE", default="vmmaster_commands")
RABBITMQ_SESSION_QUEUE = env.str("RABBITMQ_SESSION_QUEUE", default="vmmaster_session")
RABBITMQ_HEARTBEAT = env.int("RABBITMQ_HEARTBEAT", default=10)
RABBITMQ_REQUEST_TIMEOUT = env.int("", default=60)
RABBITMQ_PREFETCH_COUNT = env.int("RABBITMQ_REQUEST_TIMEOUT", default=1)
BACKEND_REQUEST_TIMEOUT = env.int("BACKEND_REQUEST_TIMEOUT", default=120)
SELENIUM_PORT = 4455

# database
DATABASE = env.str("DATABASE", default="postgresql://user:password@localhost/db")

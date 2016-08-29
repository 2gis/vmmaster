import logging
import logging.config
import logging.handlers
from core.logger import setup_logging

log = logging.getLogger(__name__)

STATIC_FOLDERS = 'frontend/static'

# logging
LOG_TYPE = "plain"
LOG_LEVEL = "DEBUG"
LOGGING = setup_logging(log_type=LOG_TYPE, log_level=LOG_LEVEL)

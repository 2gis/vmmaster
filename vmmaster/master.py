# depends on packages: kvm

from vmmaster.core.server.server import VMMasterServer
from vmmaster.core.logger import setup_logging, log
from vmmaster.core.config import setup_config, config

setup_config('/home/vmmaster/vmmaster/config.py')
setup_logging(config.LOG_DIR)

server_address = ('', config.PORT)
server = VMMasterServer(server_address)

log.info('Starting server, use <Ctrl-C> to stop')
try:
    server.run()
except KeyboardInterrupt:
    log.info("shutting down...")
    del server
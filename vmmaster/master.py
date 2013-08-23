# depends on packages: kvm

from vmmaster.core.server.server import VMMasterServer
from vmmaster.core.logger import setup_logging

setup_logging("/tmp/logs/")
server_address = ('', 9000)
server = VMMasterServer(server_address)

print 'Starting server, use <Ctrl-C> to stop'
try:
    server.run()
except KeyboardInterrupt:
    print "shutting down..."
# depends on packages: kvm
from vmmaster.core.server.server import VMMasterServer


server_address = ('', 9000)
server = VMMasterServer(server_address)
print 'Starting server, use <Ctrl-C> to stop'
server.run()

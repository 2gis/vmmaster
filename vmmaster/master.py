from vmmaster.core.server.server import VMMasterServer

server_address = ('', 9000)
server = VMMasterServer(server_address)
server.run()

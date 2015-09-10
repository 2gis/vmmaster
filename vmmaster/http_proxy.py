from twisted.internet import reactor, protocol
from twisted.web.resource import Resource
from twisted.web.http import HTTPChannel, HTTPClient, Request
from twisted.web.server import NOT_DONE_YET


class HTTPChannelWithClient(HTTPChannel):
    requestFactory = Request

    def __init__(self):
        HTTPChannel.__init__(self)
        self.client = None

    # Client => Proxy
    def dataReceived(self, data):
        if self.client:
            self.client.write(data)
        else:
            HTTPChannel.dataReceived(self, data)

    # Proxy => Client
    def write(self, data):
        self.transport.write(data)


class ClientProtocol(HTTPClient):
    def __init__(self, factory, command, rest, version, headers, data):
        self.factory = factory
        self.command = command
        self.rest = rest
        self.headers = headers
        self.data = data
        self.version = version

    def connectionMade(self):
        self.factory.server.client = self
        self.sendCommand(self.command, self.rest, self.version)
        for header, value in self.headers.items():
            self.sendHeader(header, value)
        self.endHeaders()
        self.write(self.data)

    def sendCommand(self, command, path, version):
        self.transport.writeSequence(
            [command, b' ', path, b' ', version, '\r\n'])

    # Server => Proxy
    def dataReceived(self, data):
        self.factory.server.write(data)

    # Proxy => Server
    def write(self, data):
        if data:
            self.transport.write(data)


class ClientFactory(protocol.ClientFactory):
    protocol = ClientProtocol

    def __init__(self, request, rest):
        headers = request.getAllHeaders().copy()
        request.content.seek(0, 0)
        s = request.content.read()
        self.request = request
        self.method = request.method
        self.rest = rest
        self.headers = headers
        self.data = s
        self.version = request.clientproto

    def buildProtocol(self, addr):
        return self.protocol(
            self,
            self.method, self.rest, self.version,
            self.headers,
            self.data)

    def clientConnectionFailed(self, connector, reason):
        self.request.write(
            "Request forwarding failed:\n" + reason.getErrorMessage())
        self.request.finish()


class ProxyResource(Resource):
    def __init__(self, app):
        self.app = app

    isLeaf = True

    def _parse_uri(self, uri):
        parts = uri.split("/")
        session_id = int(parts[parts.index("session") + 1])
        port = int(parts[parts.index("port") + 1])
        dest = parts[parts.index("port") + 2:]
        dest = "/".join(dest)
        if not dest.endswith("/"):
            dest += "/"
        return session_id, port, dest

    def process(self, request):
        try:
            session_id, port, dest = self._parse_uri(request.uri)
        except:
            raise Exception(
                "Could'nt parse request uri, "
                "make sure you request uri has "
                "/proxy/session/<session_id>/port/<port_number>/<destination>")

        with self.app.app_context():
            session = self.app.sessions.get_session(session_id)

        host = session.endpoint_ip
        client_factory = ClientFactory(request, dest)
        client_factory.server = request.channel
        reactor.connectTCP(host, port, client_factory)

        return NOT_DONE_YET

    def render(self, request):
        try:
            return self.process(request)
        except Exception as e:
            request.setResponseCode(500)
            return e.message

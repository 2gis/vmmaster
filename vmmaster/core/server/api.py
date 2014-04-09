from twisted.web.server import Site
from twisted.web.resource import Resource


class StatusResource(Resource):
    isLeaf = True
    numberRequests = 0

    def render(self, request):
        clone_list = self.server.clone_factory.clone_list.list
        request.setHeader("content-type", "text/plain")
        return str(clone_list)


class ApiServer(Site):
    root = Resource()

    def setup_root(self):
        self.root.server = self
        self.root.putChild('status', StatusResource())

    def __init__(self, clone_factory, sessions):
        Site.__init__(self, self.root)
        self.clone_factory = clone_factory
        self.sessions = sessions
        self.setup_root()
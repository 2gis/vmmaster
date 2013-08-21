class Sessions(object):
    def __init__(self):
        self.map = {}

    def add_session(self, sessionId, ip):
        self.map[sessionId] = ip

    def get_ip(self, sessionId):
        return self.map[sessionId]

    def delete_session(self, sessionId):
        del self.map[sessionId]
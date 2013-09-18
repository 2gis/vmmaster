class Sessions(object):
    def __init__(self):
        self.map = {}

    def add_session(self, sessionId, clone):
        self.map[sessionId] = clone

    def get_clone(self, sessionId):
        return self.map[sessionId]

    def delete_session(self, sessionId):
        del self.map[sessionId]
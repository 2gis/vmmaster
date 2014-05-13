class Sessions(object):
    def __init__(self):
        self.map = {}

    def add_session(self, session_id, clone, selenium_session):
        self.map[session_id] = (clone, selenium_session)

    def get_clone(self, session_id):
        return self.map[session_id][0]

    def get_selenium_session(self, session_id):
        return self.map[session_id][1]

    def delete_session(self, session_id):
        del self.map[session_id]
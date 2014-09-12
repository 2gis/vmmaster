from flask import jsonify

from .platforms import Platforms
from .exceptions import SessionException
from .session_queue import q


def render_json(result, code=200):
    response = dict()
    response['metacode'] = code
    response['result'] = result
    return jsonify(response)


class ApiHandler(object):
    _headers = None
    _body = None

    _reply_code = None
    _reply_headers = None
    _reply_body = None

    _log_step = None
    _session_id = None

    def __init__(self, sessions):
        self._sessions = sessions

    def platforms(self):
        platfroms = list(Platforms.platforms.keys())
        return render_json({'platforms': platfroms})

    def sessions(self):
        sessions = list()
        for id, session in self._sessions:
            sessions.append({
                "id": id,
                "name": session.name,
                "platform": session.platform,
                "duration": session.duration
            })
        return render_json({'sessions': sessions})

    def queue(self):
        queue = dict()
        for i, job in enumerate(q):
            queue[i] = job.args[0]

        return render_json(queue)

    def stop_session(self, id):
        try:
            session = self._sessions.get_session(id)
        except SessionException:
            return render_json(result="Session not found", code=404)
        session.close()
        return render_json("")
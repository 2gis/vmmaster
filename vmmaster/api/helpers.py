# coding: utf-8

from flask import current_app
from vmmaster.core.exceptions import SessionException


def get_session(session_id):
    try:
        session = current_app.sessions.get_session(session_id)
    except SessionException:
        session = None
    return session


def get_sessions():
    from vmmaster.core.db import database
    sessions = list()
    for session in database.get_sessions():
        sessions.append(session.info)
    return sessions


def get_queue():
    from vmmaster.core.db import database
    queue = list()
    for session in database.get_queue():
        queue.append(session.info)
    return queue


def get_user(user_id):
    from vmmaster.core.db import database
    return database.get_user(user_id=user_id)


def regenerate_user_token(user_id):
    user = get_user(user_id)
    if user:
        return user.regenerate_token()
    return None

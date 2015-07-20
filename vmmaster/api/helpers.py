# coding: utf-8

from flask import current_app

from ..core.exceptions import SessionException
from ..core.session_queue import q
from ..core.db import database


def get_session(session_id):
    try:
        session = current_app.sessions.get_session(session_id)
    except SessionException:
        session = None
    return session


def get_sessions():
    sessions_list = list()
    for session_id, session in current_app.sessions:
        sessions_list.append(session.info)
    return sessions_list


def get_queue():
    return str(q)


def get_user(user_id):
    return database.get_user(user_id=user_id)


def regenerate_user_token(user_id):
    user = get_user(user_id)
    if user:
        return user.regenerate_token()
    return None

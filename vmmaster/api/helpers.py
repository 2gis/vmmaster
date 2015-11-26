# coding: utf-8

from flask import current_app
from core.exceptions import SessionException


def get_session(session_id):
    try:
        session = current_app.sessions.get_session(session_id)
    except SessionException:
        session = None
    return session


def get_sessions():
    sessions = list()
    for session in current_app.sessions.active():
        sessions.append(session.info)
    return sessions


def get_queue():
    queue = list()
    for session in current_app.sessions.waiting():
        queue.append(session.info)
    return queue


def get_user(user_id):
    return current_app.database.get_user(user_id=user_id)


def regenerate_user_token(user_id):
    user = get_user(user_id)
    if user:
        return user.regenerate_token()
    return None


def get_screenshots(session_id, log_step_id=None):
    from core.db import database
    screenshots = []

    if log_step_id:
        session_steps = [database.get_step_by_id(log_step_id)]
    else:
        session_steps = database.get_log_steps_for_session(session_id)

    for log_step in session_steps:
        if log_step.screenshot:
            screenshots.append(log_step.screenshot)

    return sorted(screenshots)


def get_screenshots_for_label(session_id, label_id):
    from core.db import database
    steps_groups = {}
    current_label = 0
    log_steps = database.get_log_steps_for_session(session_id)

    for step in reversed(log_steps):
        if label_step(step.control_line) == 'label':
            current_label = step.id

        if not steps_groups.get(current_label, None):
            steps_groups[current_label] = []

        if step.screenshot:
            steps_groups[current_label].append(step.screenshot)

    try:
        return steps_groups[label_id]
    except KeyError:
        return []


def label_step(string):
    try:
        request = string.split(" ")
        if request[0] == "POST" and request[1].endswith("/vmmasterLabel"):
            return 'label'
    except:
        return ''

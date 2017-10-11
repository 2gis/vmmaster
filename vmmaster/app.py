# coding: utf-8

import logging

from flask import json, Flask
from core.config import config

log = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        return super(JSONEncoder, self).default(obj)


class Vmmaster(Flask):
    def __init__(self, *args, **kwargs):
        from core.db import Database
        from core.sessions import Sessions

        super(Vmmaster, self).__init__(*args, **kwargs)
        self.running = True
        self.json_encoder = JSONEncoder
        self.database = Database()
        self.sessions = Sessions(self)
        self.sessions.start_workers()
        log.info("Application was started...")

    def cleanup(self):
        log.info("Cleanup...")
        try:
            self.sessions.stop_workers()
            log.info("Cleanup done")
        except:
            log.exception("Cleanup was finished with errors")

    @property
    def providers(self):
        return self.database.get_active_providers()

    def stop(self):
        self.running = False

    def match(self, dc):
        from vmmaster.matcher import SeleniumMatcher, PlatformsBasedMatcher
        for provider in self.providers:
            platforms = self.database.get_platforms(provider.id)
            matcher = SeleniumMatcher(
                platforms=provider.config,
                fallback_matcher=PlatformsBasedMatcher(platforms)
            )
            if matcher.match(dc):
                return True
        return False


def register_blueprints(app):
    from vmmaster.api import api
    from webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")

    app = Vmmaster(__name__)

    register_blueprints(app)
    return app

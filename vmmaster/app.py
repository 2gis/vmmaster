# coding: utf-8

import logging
import threading

from flask import Flask
from core.config import config
from core.utils import JSONEncoder

log = logging.getLogger(__name__)


class Vmmaster(Flask):
    balance_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        from core.db import Database
        from core.sessions import Sessions

        super(Vmmaster, self).__init__(*args, **kwargs)
        self.running = True
        self.json_encoder = JSONEncoder
        self.database = Database()
        self.sessions = Sessions(self.database, self.app_context)
        self.sessions.start_workers()

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

    def get_matched_platforms(self, dc):
        from vmmaster.matcher import SeleniumMatcher, PlatformsBasedMatcher
        providers_platforms, limits = {}, {}

        with self.balance_lock:
            for provider in self.providers:
                platforms = self.database.get_platforms(provider.id)
                matcher = SeleniumMatcher(
                    platforms=provider.config,
                    fallback_matcher=PlatformsBasedMatcher(platforms)
                )
                matched_platforms = matcher.get_matched_platforms(dc)
                if matched_platforms and provider.max_limit:
                    providers_platforms[provider.id] = matched_platforms
                    limits[provider.id] = provider.max_limit

            if not providers_platforms:
                return None, None

            provider_id = self.get_provider_id(limits)
            if provider_id:
                return providers_platforms[provider_id][0], provider_id

        return None, None

    def get_provider_id(self, limits):
        availables = {}

        for provider_id, limit in limits.items():
            sessions = self.sessions.active(provider_id=provider_id)
            availables[provider_id] = limit - len(sessions)

        if availables:
            max_value = max(availables.values())
            return availables.keys()[availables.values().index(max_value)]


def register_blueprints(app):
    from vmmaster.api import api
    from vmmaster.webdriver import webdriver
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(webdriver, url_prefix='/wd/hub')


def create_app():
    if config is None:
        raise Exception("Need to setup config.py in application directory")

    app = Vmmaster(__name__)

    register_blueprints(app)
    return app

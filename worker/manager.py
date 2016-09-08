import asyncio


class Manager(object):
    def __init__(self, app):
        self.running = False
        self.app = app


# coding: utf-8


class SessionQueue():
    def __init__(self):
        pass

    @property
    def all(self):
        from ..core.db import database
        return database.queue()

    def __str__(self):
        res = []
        for vm in self.all:
            res.append(str(vm))
        return str(res)

    def __repr__(self):
        return self.all


q = SessionQueue()

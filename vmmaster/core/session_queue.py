# coding: utf-8


class SessionQueue():
    def __init__(self):
        pass

    @property
    def all(self):
        from ..core.db import database
        return database.queue()

    @property
    def waiting(self):
        from ..core.db import database
        return database.vm_waiting()

    def __str__(self):
        res = []
        for vm in self.waiting:
            res.append(str(vm))
        return str(res)

    def __repr__(self):
        return self.all


q = SessionQueue()

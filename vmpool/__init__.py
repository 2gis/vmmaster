# coding: utf-8

from datetime import datetime
from core.db import models


class VirtualMachine(models.Endpoint):
    def __init__(self, name, platform, provider_id):
        super(VirtualMachine, self).__init__(name, platform, provider_id)
        self.name = name
        self.ip = None
        self.mac = None
        self.platform = platform
        self.created_time = datetime.now()
        self.save()

    @property
    def info(self):
        return {
            "name": str(self.name),
            "ip": str(self.ip),
            "platform": str(self.platform),
            "created_time": str(self.created_time),
            "used_time": str(self.used_time) if self.used_time else None,
            "deleted_time": str(self.deleted_time) if self.deleted_time else None,
            "used": str(self.used),
            "ready": str(self.ready),
            "deleted": str(self.deleted)
        }

    def create(self):
        pass

    def delete(self):
        self.deleted_time = datetime.now()
        self.deleted = True
        self.save()

    def mark_as_used(self):
        self.used_time = datetime.now()
        self.used = True
        self.save()

    def is_preloaded(self):
        return 'preloaded' in self.name

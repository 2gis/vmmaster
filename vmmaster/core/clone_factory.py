import logging

from vmmaster.core.clone import Clone
from vmmaster.core.connection import Virsh
from vmmaster.core.logger import log


class PlatformException(Exception):
    pass


class CloneFactory(object):
    def __init__(self):
        log.info("initializing clone factory")
        self.conn = Virsh()
        self.clone_list = {}
        for origin in self.conn.listDefinedDomains():
            self.clone_list[origin] = []

        log.info("starting with " + str(self.clone_list))

    def delete(self):
        log.info("deleting clone factory")
        running_clones = []
        for platform in self.clone_list:
            for clone in self.clone_list[platform]:
                running_clones.append(clone)

        for clone in running_clones:
            self.utilize_clone(clone)

    def create_clone(self, platform):
        if platform not in self.clone_list:
            raise PlatformException("no such a platform")

        ### @todo: limit by count of clones

        clone = Clone(len(self.clone_list[platform]), platform)
        self.clone_list[platform].append(clone)
        try:
            return clone.create()
        except:
            self.utilize_clone(clone)

    def utilize_clone(self, clone):
        self.clone_list[clone.platform].remove(clone)
        clone.delete()
        log.debug(self.clone_list)
        return
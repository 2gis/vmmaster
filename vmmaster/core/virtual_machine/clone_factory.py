from .clone import Clone

from ..config import config
from ..logger import log
from ..dispatcher import dispatcher, Signals


class CloneList(object):
    def __init__(self):
        self.__clones = dict()
        self.__clone_numbers = [i for i in reversed(range(0, config.MAX_VM_COUNT))]

    def add_clone(self, clone):
        if not self.__clones.get(clone.platform, None):
            self.__clones[clone.platform] = list()

        self.__clones[clone.platform].append(clone)

    def remove_clone(self, clone):
        if self.__clones.get(clone.platform, None):
            self.__clones[clone.platform].remove(clone)

    @property
    def clones(self):
        clones = []
        for platform in self.__clones:
            clones += self.__clones[platform]

        return clones

    @property
    def clone_list(self):
        return self.__clones

    @property
    def total_count(self):
        return len(self.clones)

    def get_clone_number(self, platform):
        if self.__clones.get(platform, None):
            return len(self.__clones.get(platform))
        else:
            return 0


class CloneFactory(object):
    def __init__(self):
        log.info("initializing clone factory")
        self.clone_list = CloneList()
        dispatcher.connect(self.__remove_clone, signal=Signals.DELETE_VIRTUAL_MACHINE, sender=dispatcher.Any)

    def delete(self):
        log.info("deleting clone factory")
        running_clones = self.clone_list.clones

        for clone in running_clones:
            clone.delete()

        dispatcher.disconnect(self.__remove_clone, signal=Signals.DELETE_VIRTUAL_MACHINE, sender=dispatcher.Any)

    def create_clone(self, origin):
        clone = Clone(self.clone_list.get_clone_number(origin.name), origin)
        try:
            clone = clone.create()
        except Exception:
            clone.delete()
            raise

        self.clone_list.add_clone(clone)
        return clone

    def __remove_clone(self, sender):
        self.clone_list.remove_clone(sender)

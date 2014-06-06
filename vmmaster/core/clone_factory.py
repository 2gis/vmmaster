import time

from .clone import Clone
from .connection import Virsh
from .config import config
from .logger import log
from .dispatcher import dispatcher, Signals
from .exceptions import PlatformException, ClonesException


class CloneList(object):
    def __init__(self):
        self.list = dict()
        conn = Virsh()

        self.__clone_numbers = [i for i in reversed(range(0, config.MAX_CLONE_COUNT))]

        for platform in conn.listDefinedDomains():
            self.list[platform] = []

        log.debug("starting with " + str(self.list))

    def _check_platform(self, platform):
        if platform not in self.list:
            raise PlatformException("no such a platform")

    def _check_clone_count(self):
        if len(self.__clone_numbers) == 0:
            raise ClonesException("maximum clones count already running")

    def _check_clone(self, clone):
        self._check_platform(clone.platform)
        self._check_clone_count()

    def add_clone(self, clone):
        self.list[clone.platform].append(clone)

    def remove_clone(self, clone):
        self.list[clone.platform].remove(clone)
        self.add_free_clone_number(clone.number)

    def get_clones(self, platform):
        return self.list[platform]

    def get_all_clones(self):
        clones = []
        for platform in self.get_platforms():
            clones += self.get_clones(platform)

        return clones

    @property
    def total_count(self):
        return len(self.get_all_clones())

    def clones_count(self, platform):
        return len(self.list[platform])

    def get_platforms(self):
        return self.list

    def get_free_clone_number(self, platform):
        self._check_platform(platform)
        self._check_clone_count()
        clone_numbers = self.__clone_numbers
        return clone_numbers.pop()

    def add_free_clone_number(self, number):
        self.__clone_numbers.append(number)


class CloneFactory(object):
    def __init__(self):
        log.info("initializing clone factory")
        dispatcher.connect(self.utilize_clone, signal=Signals.DELETE_CLONE, sender=dispatcher.Any)
        self.clone_list = CloneList()

    def delete(self):
        log.info("deleting clone factory")
        running_clones = self.clone_list.get_all_clones()

        for clone in running_clones:
            self.utilize_clone(clone)

        del self

    def create_clone(self, platform):
        clone = Clone(self.clone_list.get_free_clone_number(platform), platform)
        self.clone_list.add_clone(clone)

        try:
            clone = clone.create()
        except Exception:
            self.utilize_clone(clone)
            raise

        return clone

    def utilize_clone(self, clone, timeouted=False):
        if timeouted:
            log.warning("TIMEOUT {clone}".format(clone=clone.name))
        self.clone_list.remove_clone(clone)
        clone.delete()
        return
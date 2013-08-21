# depends on packages: kvm
import os

from vmmaster.core.network.network import Network
from vmmaster.core.clone import Clone


class CloneFactory(object):
    clone_list = []

    def __init__(self):
        pass

    def __del__(self):
        self.network.__del__()
        for clone_name, clone_files in self.clone_list:
            domain = self.conn.lookupByName(clone_name)
            domain.destroy()
            domain.undefine()
            for file in clone_files:
                try:
                    os.remove(file)
                except (OSError, AttributeError):
                    pass

    def create_clone(self, platform):
        clone = Clone(len(self.clone_list), platform)
        return clone.create()
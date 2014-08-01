import unittest

from vmmaster.core.virtual_machine.clone_factory import CloneList
from vmmaster.core.virtual_machine.clone import Clone
from vmmaster.core.platform import Platforms
from vmmaster.core.config import setup_config, config


class TestCloneList(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        config.MAX_VM_COUNT = 5
        platforms = Platforms()
        self.origin1 = platforms.platforms.values()[0]
        self.origin2 = platforms.platforms.values()[1]
        platforms.delete()
        self.clone_list = CloneList()

    def test_add_clone(self):
        clones = [Clone(i, self.origin1) for i in range(5)]
        for clone in clones:
            self.clone_list.add_clone(clone)

        self.assertEquals(self.clone_list.total_count, 5)
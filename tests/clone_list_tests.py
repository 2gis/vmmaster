import unittest

from vmmaster.core.clone_factory import CloneList
from vmmaster.core.clone import Clone
from vmmaster.core.config import setup_config, config


class TestCloneList(unittest.TestCase):
    def setUp(self):
        setup_config('config.py')
        config.MAX_CLONE_COUNT = 5
        self.clone_list = CloneList()

    def tearDown(self):
        pass

    def test_clone_numbers(self):
        platform_ubuntu = "ubuntu-13.04-x64"
        clones = [Clone(self.clone_list.get_free_clone_number(platform_ubuntu), platform_ubuntu) for i in range(5)]
        clone_numbers = [clone.number for clone in clones]
        self.assertEquals(clone_numbers, [0, 1, 2, 3, 4])

    def test_clone_add(self):
        platform_ubuntu = "ubuntu-13.04-x64"
        clones = [Clone(self.clone_list.get_free_clone_number(platform_ubuntu), platform_ubuntu) for i in range(5)]
        for clone in clones:
            self.clone_list.add_clone(clone)

        self.assertEquals(self.clone_list.total_count, 5)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCloneList)
    unittest.TextTestRunner(verbosity=2).run(suite)
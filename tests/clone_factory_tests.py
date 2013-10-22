import unittest

from vmmaster.core.clone_factory import CloneFactory
from vmmaster.core.clone_factory import ClonesException
from vmmaster.core.clone import Clone
from vmmaster.core.config import setup_config, config


def delete(self):
    timer = self.get_timer()
    timer.stop()
    del self


def create(self):
    return self


class TestCloneFactory(unittest.TestCase):
    def setUp(self):
        self.platform_ubuntu = "ubuntu-13.04-x64"
        self.platform_windows = "windows-7-x64"
        setup_config('config.py')
        config.MAX_CLONE_COUNT = 5
        self.clone_factory = CloneFactory()
        Clone.create = create
        Clone.delete = delete
        # Clone.drive_path = "None"
        # Clone.dumpxml_file = "None"

    def tearDown(self):
        self.clone_factory.delete()

    def test_clone_creation(self):
        clone = self.clone_factory.create_clone(self.platform_ubuntu)
        self.assertTrue(clone)
        clone.delete()

    def test_clone_utilization(self):
        clone = self.clone_factory.create_clone(self.platform_ubuntu)
        self.clone_factory.utilize_clone(clone)
        self.assertFalse(clone in self.clone_factory.clone_list.get_all_clones())
        self.assertEqual(self.clone_factory.clone_list.total_count, 0)

    def test_clone_creation_raise_exception_max_clones(self):
        config.MAX_CLONE_COUNT = 2
        self.clone_factory = CloneFactory()

        self.clone_factory.create_clone(self.platform_ubuntu)
        self.clone_factory.create_clone(self.platform_windows)
        with self.assertRaises(ClonesException) as cm:
            self.clone_factory.create_clone(self.platform_windows)

        the_exception = cm.exception
        self.assertEqual(the_exception.message, "maximum clones count already running")

    def test_clone_creation_after_utilization(self):
        ubuntu_clones = [self.clone_factory.create_clone(self.platform_ubuntu) for i in range(3)]
        windows_clones = [self.clone_factory.create_clone(self.platform_windows) for i in range(2)]
        clones = ubuntu_clones + windows_clones

        clone = clones.pop(0)
        self.clone_factory.utilize_clone(clone)
        self.assertEqual(self.clone_factory.clone_list.get_all_clones(), clones)

        new_clone = self.clone_factory.create_clone(self.platform_ubuntu)
        clones.append(new_clone)

        self.assertEqual(len(self.clone_factory.clone_list.get_all_clones()), len(clones))
        self.assertEqual(sorted(self.clone_factory.clone_list.get_all_clones()), sorted(clones))

    def test_clone_multiple_creation_and_multiple_utilization(self):
        ubuntu_clones = [self.clone_factory.create_clone(self.platform_ubuntu) for i in range(3)]
        windows_clones = [self.clone_factory.create_clone(self.platform_windows) for i in range(2)]
        clones = ubuntu_clones + windows_clones

        from random import randint
        for i in range(3):
            number = randint(0, len(clones)-1)
            clone = clones.pop(number)
            self.clone_factory.utilize_clone(clone)

        for i in range(3):
            number = randint(0, 1)
            clone = self.clone_factory.create_clone(self.platform_ubuntu if number else self.platform_windows)
            clones.append(clone)

        self.assertEqual(len(self.clone_factory.clone_list.get_all_clones()), len(clones))
        self.assertEqual(sorted(self.clone_factory.clone_list.get_all_clones()), sorted(clones))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCloneFactory)
    unittest.TextTestRunner(verbosity=2).run(suite)
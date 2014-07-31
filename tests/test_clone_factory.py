import unittest

from mock import Mock

from vmmaster.core.virtual_machine.clone_factory import CloneFactory
from vmmaster.core.config import setup_config, config
from vmmaster.core.platform import Platforms

# Mocking
from vmmaster.core import connection
connection.Virsh.__new__ = Mock()
from vmmaster.core.network import network
network.Network.__new__ = Mock()
from vmmaster.core.virtual_machine.clone import Clone
Clone.clone_origin = Mock()
Clone.define_clone = Mock()
Clone.start_virtual_machine = Mock()
Clone.drive_path = Mock()
from vmmaster.core.utils import utils
utils.delete_file = Mock()


class TestCloneFactoryCreate(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        config.MAX_VM_COUNT = 5
        self.clone_factory = CloneFactory()
        platforms = Platforms()
        self.origin1 = platforms.platforms.values()[0]
        self.origin2 = platforms.platforms.values()[1]
        platforms.delete()

    def tearDown(self):
        self.clone_factory.delete()

    def test_clone_creation(self):
        clone = self.clone_factory.create_clone(self.origin1)
        self.assertIsInstance(clone, Clone)
        self.assertTrue(clone in self.clone_factory.clone_list.clones)

    def test_clone_deletion(self):
        clone = self.clone_factory.create_clone(self.origin1)
        clone.delete()
        self.assertFalse(clone in self.clone_factory.clone_list.clones)
        self.assertEqual(self.clone_factory.clone_list.total_count, 0)

    def test_creation_after_utilization(self):
        origin1_clones = [self.clone_factory.create_clone(self.origin1) for i in range(3)]
        origin2_clones = [self.clone_factory.create_clone(self.origin2) for i in range(2)]
        clones = origin1_clones + origin2_clones

        clone = clones.pop(0)
        clone.delete()
        self.assertEqual(sorted(self.clone_factory.clone_list.clones), sorted(clones))

        new_clone = self.clone_factory.create_clone(self.origin1)
        clones.append(new_clone)

        self.assertEqual(len(self.clone_factory.clone_list.clones), len(clones))
        self.assertEqual(sorted(self.clone_factory.clone_list.clones), sorted(clones))

    def test_clone_multiple_creation_and_multiple_utilization(self):
        origin1_clones = [self.clone_factory.create_clone(self.origin1) for i in range(3)]
        origin2_clones = [self.clone_factory.create_clone(self.origin2) for i in range(2)]
        clones = origin1_clones + origin2_clones

        from random import randint
        for i in range(3):
            number = randint(0, len(clones)-1)
            clone = clones.pop(number)
            clone.delete()

        for i in range(3):
            number = randint(0, 1)
            clone = self.clone_factory.create_clone(self.origin1 if number else self.origin2)
            clones.append(clone)

        self.assertEqual(len(self.clone_factory.clone_list.clones), len(clones))
        self.assertEqual(sorted(self.clone_factory.clone_list.clones), sorted(clones))

    def test_parallel_clone_creation(self):
        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=1)
        deffered1 = pool.apply_async(self.clone_factory.create_clone, (self.origin1, ))
        deffered2 = pool.apply_async(self.clone_factory.create_clone, (self.origin1, ))
        clone1 = deffered1.get()
        clone2 = deffered2.get()
        clones = [clone1, clone2]

        self.assertEqual(len(self.clone_factory.clone_list.clones), len(clones))
        self.assertEqual(sorted(self.clone_factory.clone_list.clones), sorted(clones))


class TestCloneFactoryDelete(unittest.TestCase):
    def setUp(self):
        setup_config('data/config.py')
        config.MAX_VM_COUNT = 5
        self.clone_factory = CloneFactory()
        platforms = Platforms()
        self.origin1 = platforms.platforms.values()[0]
        self.origin2 = platforms.platforms.values()[1]
        platforms.delete()

    def test_clone_factory_delete(self):
        clones = [self.clone_factory.create_clone(self.origin1) for i in range(3)]
        [clone.delete() for clone in clones]
        self.clone_factory.delete()
        self.assertEqual([], self.clone_factory.clone_list.clones)
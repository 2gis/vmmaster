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

    def test_get_clone_number_no_clones(self):
        clone = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        self.assertEquals(0, clone.number)

    def test_clone_list_reservation(self):
        reservation = self.clone_list._reserve(self.origin1.name)
        self.assertTrue(reservation in self.clone_list.clone_list[self.origin1.name])

    def test_get_clone_number_one_clone(self):
        reservation = self.clone_list._reserve(self.origin1.name)
        reservation.number = 0
        self.clone_list.add_clone(Clone(0, self.origin1))
        clone = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        self.assertEquals(1, clone.number)

    def test_add_clone(self):
        clones = [Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1) for i in range(5)]
        for clone in clones:
            self.clone_list.add_clone(clone)

        self.assertEquals(self.clone_list.total_count, 5)

    def test_get_clone_number_several_clones(self):
        for i in range(3):
            clone = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
            self.clone_list.add_clone(clone)

        clones_numbers = [clone.number for clone in self.clone_list.clones]
        self.assertEquals([0, 1, 2], clones_numbers)

    def test_get_clone_number_parallel(self):
        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=1)
        deffered1 = pool.apply_async(self.clone_list.get_clone_number, (self.origin1, ))
        deffered2 = pool.apply_async(self.clone_list.get_clone_number, (self.origin1, ))
        number1 = deffered1.get()
        number2 = deffered2.get()

        self.assertEqual([0, 1], [number1, number2])

    def test_get_clone_number_after_deletion(self):
        reservation = self.clone_list._reserve(self.origin1.name)
        reservation.number = 0
        self.clone_list.add_clone(Clone(0, self.origin1))
        clone1 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        self.clone_list.add_clone(clone1)
        self.clone_list.remove_clone(clone1)
        clone2 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        self.assertEquals(1, clone2.number)

    def test_get_clone_number_after_deletion_empty_list(self):
        reservation = self.clone_list._reserve(self.origin1.name)
        reservation.number = 0
        clone1 = Clone(0, self.origin1)
        self.clone_list.add_clone(clone1)
        self.clone_list.remove_clone(clone1)
        clone2 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        self.assertEquals(0, clone2.number)

    def test_get_clone_number_different_platforms(self):
        clone_origin1_0 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        clone_origin2_0 = Clone(self.clone_list.get_clone_number(self.origin2.name), self.origin2)
        self.assertEquals(0, clone_origin1_0.number)
        self.assertEquals(0, clone_origin2_0.number)

    def test_get_clone_number_different_platforms_several_clones(self):
        clone_origin1_0 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        clone_origin2_0 = Clone(self.clone_list.get_clone_number(self.origin2.name), self.origin2)
        self.clone_list.add_clone(clone_origin1_0)
        self.clone_list.add_clone(clone_origin2_0)
        clone_origin1_1 = Clone(self.clone_list.get_clone_number(self.origin1.name), self.origin1)
        clone_origin2_1 = Clone(self.clone_list.get_clone_number(self.origin2.name), self.origin2)
        self.assertEquals(1, clone_origin1_1.number)
        self.assertEquals(1, clone_origin2_1.number)
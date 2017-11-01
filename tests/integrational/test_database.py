# -*- coding: utf-8 -*-

import time
from unittest import TestCase
from multiprocessing.pool import ThreadPool

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

from core.db import Database
from core.config import setup_config, config


Base = declarative_base()


class MyModel(Base):
    __tablename__ = 'my_models'

    id = Column(Integer, primary_key=True)
    name = Column(String)


class Parent(Base):
    __tablename__ = 'parents'

    id = Column(Integer, primary_key=True)
    name = Column(String)


class Child(Base):
    __tablename__ = 'children'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    parent_id = Column(ForeignKey('parents.id'))

    parent = relationship("Parent", backref=backref("children", enable_typechecks=False), lazy='subquery')

    def __init__(self, name, parent):
        self.parent = parent
        self.name = name


class TestDatabaseBasicMethods(TestCase):
    @classmethod
    def setUpClass(cls):
        setup_config('data/config.py')
        cls.db = Database(config.DATABASE)
        Base.metadata.drop_all(cls.db.engine)
        Base.metadata.create_all(cls.db.engine)

        cls.size = 20

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.db.engine)

    def setUp(self):
        self.assertEqual(len(self.select_all(Child)), 0)
        self.assertEqual(len(self.select_all(Parent)), 0)
        self.assertEqual(len(self.select_all(MyModel)), 0)

    def tearDown(self):
        self.truncate_all_tables()

    def truncate_all_tables(self):
        s = self.db.DBSession()
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
            s.commit()
        s.close()

    def select_all(self, model):
        session = self.db.DBSession()
        res = session.query(model).all()
        session.close()
        return res

    def select_all_children(self, parent):
        session = self.db.DBSession()
        res = session.query(Child).filter_by(parent_id=parent.id).all()
        session.close()
        return res

    def get_objects(self, obj):
        session = self.db.DBSession()
        res = session.query(MyModel).filter_by(id=obj.id).all()
        session.close()
        return res

    def count(self, obj):
        return len(self.get_objects(obj))

    def test_add_obj(self):
        """
        Test adding objects
            Add new object
            Check count = 1
            Delete object
            Check count = 0
            Delete obj
        """
        obj = MyModel(name='test_add_obj')
        self.assertEqual(self.count(obj), 0)
        self.db.add(obj)
        self.assertEqual(self.count(obj), 1)
        self.db.delete(obj)
        self.assertEqual(self.count(obj), 0)

    def test_update_obj(self):
        """
        Test updating objects
            Add new object
            Update object field
            Check state still old in another session
            Update object
            Check for new state in another session
            Delete obj
        """
        obj = MyModel(name='test_update_obj')
        self.assertEqual(self.count(obj), 0)
        self.db.add(obj)
        self.assertEqual(self.count(obj), 1)
        obj.name = 'test_update_obj_updated'

        s = self.db.DBSession()
        obj2 = s.query(MyModel).get(obj.id)
        s.close()
        self.assertEqual(obj2.name, 'test_update_obj')

        self.db.update(obj)
        self.assertEqual(self.count(obj), 1)

        s = self.db.DBSession()
        obj2 = s.query(MyModel).get(obj.id)
        s.close()
        self.assertEqual(obj2.name, 'test_update_obj_updated')

        self.db.delete(obj)
        self.assertEqual(self.count(obj), 0)

    def test_refresh_obj(self):
        """
        Test refreshing objects
            Add new object
            Get object copy from DB in another session
            Modify object in another session
            Check object still the same in old session
            Refresh object in old session
            Check for new state
            Delete obj
        """
        obj = MyModel(name='test_refresh_obj')

        self.assertEqual(self.count(obj), 0)

        self.db.add(obj)
        self.assertEqual(self.count(obj), 1)

        s = self.db.DBSession()
        obj_copy = s.query(MyModel).get(obj.id)
        s.close()
        obj_copy.name = 'test_refresh_obj_changed'
        self.db.update(obj_copy)

        self.assertEqual(self.count(obj), 1)

        self.assertEqual(obj.name, 'test_refresh_obj')
        self.db.refresh(obj)
        self.assertEqual(obj.name, 'test_refresh_obj_changed')

        self.db.delete(obj)
        self.assertEqual(self.count(obj), 0)

    def execute_parallel(self, func, params):
        thread_pool = ThreadPool(processes=self.size)
        try:
            tasks = thread_pool.map(func, params)
            for task in tasks:
                if task:
                    task.join()
        finally:
            thread_pool.terminate()

    def get_session_from_obj(self, obj):
        return self.db.session_maker.object_session(obj)

    def create_parent(self):
        parent = Parent(name='first')
        self.db.add(parent)
        self.assertEqual(len(self.select_all(Parent)), 1)
        return parent

    def create_children(self, parent):
        child_names = ['child_{}'.format(item) for item in range(1, self.size + 1)]

        def add_child(name):
            try:
                child = Child(name, parent)
                self.db.add(child)
            except:
                pass

        self.execute_parallel(add_child, child_names)

    def test_parallel_add(self):
        """
        Test adding objects to parent in parallel threads
            - Create Parent instance
            - Create few Child instances and attach them to parent in parallel threads
        Expected:
            - all child objects exists in db
            - parent and children objects not attached to any sessions
        """
        parent = self.create_parent()
        self.create_children(parent)

        children = self.select_all_children(parent)
        self.assertEqual(len(children), self.size)
        self.assertIsNone(self.get_session_from_obj(parent))

        dbsessions = map(self.get_session_from_obj, children)
        self.assertFalse(any(dbsessions))
        self.assertIsNone(self.get_session_from_obj(parent))

    def test_parallel_update(self):
        """
        Test updating objects in parallel threads
            - Create Parent and Child instances
            - Update Child instances name in parallel threads
        Expected:
            - all child objects updated
            - parent and children objects not attached to any sessions
        """
        parent = self.create_parent()
        self.create_children(parent)

        def update_child_name(child):
            try:
                child.name += "_updated"
                self.db.update(child)
            except:
                pass

        self.execute_parallel(update_child_name, self.select_all_children(parent))

        children = self.select_all_children(parent)
        self.assertEqual(len(children), self.size)
        self.assertIsNone(self.get_session_from_obj(parent))
        self.assertEqual(len(filter(lambda x: '_updated' not in x.name, children)), 0)

        dbsessions = map(self.get_session_from_obj, children)
        self.assertFalse(any(dbsessions))
        self.assertIsNone(self.get_session_from_obj(parent))

    def test_parallel_refresh(self):
        """
        Test refreshing objects in parallel threads
            - Refresh Child instances in parallel threads
        Expected:
            - all child objects refreshed
            - parent and children objects not attached to any sessions
        """
        parent = self.create_parent()
        self.create_children(parent)

        def refresh_child(child):
            try:
                self.db.refresh(child)
            except:
                pass

        self.execute_parallel(refresh_child, self.select_all_children(parent))

        children = self.select_all_children(parent)
        self.assertEqual(len(children), self.size)
        self.assertIsNone(self.get_session_from_obj(parent))
        # self.assertEqual(len(filter(lambda x: '_updated' not in x.name, children)), 0)

        dbsessions = map(self.get_session_from_obj, children)
        self.assertFalse(any(dbsessions))
        self.assertIsNone(self.get_session_from_obj(parent))

    def test_parallel_delete(self):
        """
        Test deleting objects in parallel threads
            - Delete Child instances in parallel threads
        Expected:
            - Child instances deleted
            - parent not attached to any sessions
        """
        parent = self.create_parent()
        self.create_children(parent)

        def delete_child(child):
            try:
                self.db.delete(child)
            except:
                pass

        self.execute_parallel(delete_child, self.select_all_children(parent))

        children = self.select_all_children(parent)
        self.assertEqual(len(children), 0)
        self.assertIsNone(self.get_session_from_obj(parent))

    def test_change_single_object_in_parallel_threads(self):
        """
        Test object state refresh and save in parallel threads
        - Change field in one thread, wait for changes in another
        Expected: field changed
        """
        obj = MyModel(name='name')
        self.db.add(obj)
        self.assertEqual(self.count(obj), 1)
        self.assertEqual(obj.name, 'name')

        def get_obj_by_id(_id):
            s = self.db.DBSession()
            _obj = s.query(MyModel).get(_id)
            s.close()
            return _obj

        def first(_id):
            _obj = get_obj_by_id(_id)
            _obj.name += '_changed'
            time.sleep(1)
            self.db.update(_obj)
            return _obj

        def second(_id):
            _obj = get_obj_by_id(_id)
            self.assertEqual(_obj.name, 'name')
            start = time.time()
            timeout = 5
            while time.time() - start < timeout:
                if _obj.name == 'name_changed':
                    self.db.update(_obj)
                    break
                self.db.refresh(_obj)
                time.sleep(0.1)

            return _obj

        pool = ThreadPool(2)
        t1 = pool.apply_async(first, args=(obj.id,))
        t2 = pool.apply_async(second, args=(obj.id,))
        t1.wait()
        t2.wait()
        obj1 = t1.get()
        obj2 = t2.get()
        self.assertEqual(obj1.name, 'name_changed')
        self.assertEqual(obj2.name, 'name_changed')

        self.db.delete(obj)
        self.assertEqual(self.count(obj), 0)

# -*- coding: utf-8 -*-

from unittest import TestCase

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from core.db import Database


Base = declarative_base()


class MyModel(Base):
    __tablename__ = 'my_models'

    id = Column(Integer, primary_key=True)
    name = Column(String)


class TestDatabase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database('sqlite:///test_database.sqlite', sqlite=True)
        MyModel.metadata.create_all(cls.db.engine)

    @classmethod
    def tearDownClass(cls):
        pass

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

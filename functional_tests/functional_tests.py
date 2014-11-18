# coding: utf-8

import unittest
from StringIO import StringIO

from multiprocessing.pool import ThreadPool

from tests.test_normal import TestPositiveCase, TestRunSriptOnSessionCreation


class TestCase(unittest.TestCase):
    def setUp(self):
        self.loader = unittest.TestLoader()
        self.runner = unittest.TextTestRunner(stream=StringIO())
        self.stream = StringIO()

    def test_positive_case(self):
        suite = self.loader.loadTestsFromTestCase(TestPositiveCase)
        result = self.runner.run(suite)
        self.assertEqual(2, result.testsRun)
        self.assertEqual(1, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)
        self.assertEqual("test_error", result.errors[0][0]._testMethodName)

    def test_run_script_on_session_creation(self):
        suite = self.loader.loadTestsFromTestCase(TestRunSriptOnSessionCreation)
        result = self.runner.run(suite)
        self.assertEqual(1, result.testsRun)
        self.assertEqual(0, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)

    def test_two_same_tests_parallel_run(self):
        suite1 = unittest.TestSuite()
        suite1.addTest(TestPositiveCase("test_google"))
        suite2 = unittest.TestSuite()
        suite2.addTest(TestPositiveCase("test_google"))

        pool = ThreadPool(2)
        deffered1 = pool.apply_async(self.runner.run, args=(suite1,))
        deffered2 = pool.apply_async(self.runner.run, args=(suite2,))
        deffered1.wait()
        deffered2.wait()
        result1 = deffered1.get()
        result2 = deffered2.get()

        self.assertEqual(1, result1.testsRun)
        self.assertEqual(1, result2.testsRun)
        self.assertEqual(0, len(result1.errors), result1.errors)
        self.assertEqual(0, len(result2.errors), result2.errors)
        self.assertEqual(0, len(result1.failures), result1.failures)
        self.assertEqual(0, len(result2.failures), result2.failures)


if __name__ == "__main__":
    unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromTestCase(TestCase))
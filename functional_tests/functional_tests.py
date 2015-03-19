# coding: utf-8

import unittest
from StringIO import StringIO

from multiprocessing.pool import ThreadPool

from tests.test_normal import TestPositiveCase, TestRunScriptOnSessionCreation
from tests.test_normal import TestParallelSessions1, TestParallelSessions2

import subprocess
from os import setsid, killpg
from signal import SIGTERM
from netifaces import ifaddresses, AF_INET
from ConfigParser import RawConfigParser


class TestCaseWithMicroApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = subprocess.Popen(["tox", "-e", "run"], preexec_fn=setsid)  # Run flask micro app via tox and gunicorn
        config = RawConfigParser()
        config.read("tests/config")
        try:
            this_machine_ip = ifaddresses('eth0').setdefault(AF_INET)[0]["addr"]
        except ValueError:
            this_machine_ip = ifaddresses('wlan0').setdefault(AF_INET)[0]["addr"]
        config.set("Network", "addr", "http://%s:5000" % this_machine_ip)
        with open('tests/config', 'wb') as configfile:
            config.write(configfile)

    @classmethod
    def tearDownClass(cls):
        killpg(cls.p.pid, SIGTERM)

    def setUp(self):
        self.loader = unittest.TestLoader()
        self.runner = unittest.TextTestRunner(stream=StringIO())
        self.stream = StringIO()

    def test_positive_case(self):
        suite = self.loader.loadTestsFromTestCase(TestPositiveCase)
        result = self.runner.run(suite)
        self.assertEqual(2, result.testsRun, result.errors)
        self.assertEqual(1, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)
        self.assertEqual("test_error", result.errors[0][0]._testMethodName)

    def test_two_same_tests_parallel_run(self):
        # TODO: Добавить проверку параллельности запусков тестов
        suite1 = unittest.TestSuite()
        suite1.addTest(TestParallelSessions1("test"))
        suite2 = unittest.TestSuite()
        suite2.addTest(TestParallelSessions2("test"))

        pool = ThreadPool(2)
        deffered1 = pool.apply_async(self.runner.run, args=(suite1,))
        deffered2 = pool.apply_async(self.runner.run, args=(suite2,))
        deffered1.wait()
        deffered2.wait()
        result1 = deffered1.get()
        result2 = deffered2.get()

        self.assertEqual(1, result1.testsRun, result1.errors)
        self.assertEqual(1, result2.testsRun, result2.errors)
        self.assertEqual(0, len(result1.errors), result1.errors)
        self.assertEqual(0, len(result2.errors), result2.errors)
        self.assertEqual(0, len(result1.failures), result1.failures)
        self.assertEqual(0, len(result2.failures), result2.failures)


class TestCase(unittest.TestCase):
    def setUp(self):
        self.loader = unittest.TestLoader()
        self.runner = unittest.TextTestRunner(stream=StringIO())
        self.stream = StringIO()

    def test_run_script_on_session_creation(self):
        suite = self.loader.loadTestsFromTestCase(TestRunScriptOnSessionCreation)
        result = self.runner.run(suite)
        self.assertEqual(1, result.testsRun, result.errors)
        self.assertEqual(0, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    tests1 = unittest.TestLoader().loadTestsFromTestCase(TestCase)
    tests2 = unittest.TestLoader().loadTestsFromTestCase(TestCaseWithMicroApp)
    suite.addTests([tests1, tests2])
    res = unittest.TextTestRunner().run(suite)
    if not res.wasSuccessful():
        exit(1)

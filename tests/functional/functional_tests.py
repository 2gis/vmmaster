# coding: utf-8

import os
import unittest
import subprocess

from StringIO import StringIO
from multiprocessing.pool import ThreadPool
from os import setsid, killpg
from signal import SIGTERM
from netifaces import ifaddresses, AF_INET
from ConfigParser import RawConfigParser

from core.utils.network_utils import get_free_port


class TestCaseWithMicroApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_port = get_free_port()
        path = os.path.dirname(os.path.realpath(__file__))
        cls.p = subprocess.Popen(["gunicorn",
                                  "--log-level=warning",
                                  "-w 2",
                                  "-b 0.0.0.0:{}".format(cls.app_port),
                                  "tests.functional.app.views:app"
                                  ], preexec_fn=setsid)
        config = RawConfigParser()
        config.read("%s/tests/config" % path)
        try:
            this_machine_ip = \
                ifaddresses('eth0').setdefault(AF_INET)[0]["addr"]
        except ValueError:
            this_machine_ip = \
                ifaddresses('wlan0').setdefault(AF_INET)[0]["addr"]
        config.set("Network", "addr", "http://{}:{}".format("jenkins.autoqa.ostack.test", cls.app_port))
        with open('%s/tests/config' % path, 'wb') as configfile:
            config.write(configfile)

    @classmethod
    def tearDownClass(cls):
        killpg(cls.p.pid, SIGTERM)

    def setUp(self):
        self.loader = unittest.TestLoader()
        self.runner = unittest.TextTestRunner(stream=StringIO())
        self.stream = StringIO()

    def test_positive_case(self):
        from tests.test_normal import TestPositiveCase
        suite = self.loader.loadTestsFromTestCase(TestPositiveCase)
        result = self.runner.run(suite)
        self.assertEqual(2, result.testsRun, result.errors)
        self.assertEqual(1, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)
        self.assertEqual("test_error", result.errors[0][0]._testMethodName)

    def test_two_same_tests_parallel_run(self):
        from tests.test_normal import \
            TestParallelSessions1, TestParallelSessions2
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
        from tests.test_normal import \
            TestRunScriptOnSessionCreation
        suite = self.loader.loadTestsFromTestCase(
            TestRunScriptOnSessionCreation)
        result = self.runner.run(suite)
        self.assertEqual(1, result.testsRun, result.errors)
        self.assertEqual(0, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)

    @unittest.skip("Error \"Connection reset by peer\" in apt-get-scripts on random openstack endpoints")
    def test_run_script_with_install_package_on_session_creation(self):
        from tests.test_normal import \
            TestRunScriptWithInstallPackageOnSessionCreation
        suite = self.loader.loadTestsFromTestCase(
            TestRunScriptWithInstallPackageOnSessionCreation)
        result = self.runner.run(suite)
        self.assertEqual(1, result.testsRun, result.errors)
        self.assertEqual(0, len(result.errors), result.errors)
        self.assertEqual(0, len(result.failures), result.failures)

    @unittest.skip("Error \"Connection reset by peer\" in apt-get-scripts on random openstack endpoints")
    def test_run_script_tests_parallel_run(self):
        from tests.test_normal import\
            TestParallelSlowRunScriptOnSession1, \
            TestParallelSlowRunScriptOnSession2
        suite1 = unittest.TestSuite()
        suite1.addTest(TestParallelSlowRunScriptOnSession1("test"))
        suite2 = unittest.TestSuite()
        suite2.addTest(TestParallelSlowRunScriptOnSession2("test"))

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

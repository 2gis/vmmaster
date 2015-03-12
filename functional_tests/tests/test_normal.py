# coding: utf-8

from helpers import TestCase
from ConfigParser import RawConfigParser


class TestPositiveCase(TestCase):
    def test_micro_app(self):
        self.config = RawConfigParser()
        with open("tests/config", "r") as configfile:
            self.config.readfp(configfile)
        micro_app_addr = self.config.get("Network", "addr")
        self.driver.get(micro_app_addr)
        go_button = self.driver.find_element_by_xpath("//input[2]")
        go_button.click()

    def test_error(self):
        raise Exception('some client exception')


class TestRunScriptOnSessionCreation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desired_capabilities["runScript"] = {"script": 'echo "hello" > ~/hello_file'}
        super(TestRunScriptOnSessionCreation, cls).setUpClass()

    def test_run_script_on_session_creation(self):
        output = self.vmmaster.run_script("cat ~/hello_file").get("output")
        self.assertEqual(u"hello\n", output)


def parallel_tests_body(self):
    config = RawConfigParser()
    with open("tests/config", "r") as configfile:
        config.readfp(configfile)
    micro_app_addr = config.get("Network", "addr")
    self.driver.get(micro_app_addr)
    go_button = self.driver.find_element_by_xpath("//input[2]")
    go_button.click()


class TestParallelSessions1(TestCase):
    def test(self):
        parallel_tests_body(self)


class TestParallelSessions2(TestCase):
    def test(self):
        parallel_tests_body(self)

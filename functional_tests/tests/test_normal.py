# coding: utf-8

from helpers import TestCase


class TestPositiveCase(TestCase):
    def test_google(self):
        self.driver.get('http://google.com')
        feeling_lucky_button = self.driver.find_element_by_css_selector("#gbqfsb")
        feeling_lucky_button.click()

    def test_error(self):
        raise Exception('some client exception')


class TestRunSriptOnSessionCreation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desired_capabilities["runScript"] = {"script": 'echo "hello" > ~/hello_file'}
        super(TestRunSriptOnSessionCreation, cls).setUpClass()

    def test_run_script_on_session_creation(self):
        output = self.vmmaster.run_script("cat ~/hello_file").get("output")
        self.assertEqual(u"hello\n", output)


def parallel_tests_body(self):
    self.driver.get('http://google.com')
    feeling_lucky_button = self.driver.find_element_by_css_selector("#gbqfsb")
    feeling_lucky_button.click()


class TestParallelSessions1(TestCase):
    def test(self):
        parallel_tests_body(self)


class TestParallelSessions2(TestCase):
    def test(self):
        parallel_tests_body(self)

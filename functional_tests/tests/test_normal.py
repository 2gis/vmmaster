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
    def setUp(self):
        self.desired_caps["runScript"] = {"script": 'echo "hello"'}

    def test_run_script_on_session_creation(self):
        pass
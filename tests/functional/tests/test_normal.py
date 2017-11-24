# coding: utf-8

import os
from tests.functional.tests.helpers import TestCase
from ConfigParser import RawConfigParser

path = os.path.dirname(os.path.realpath(__file__))


class TestPositiveCase(TestCase):
    def test_micro_app(self):
        self.config = RawConfigParser()
        with open("%s/config" % path, "r") as configfile:
            self.config.readfp(configfile)
        micro_app_addr = self.config.get("Network", "addr")
        self.driver.get(micro_app_addr)
        go_button = self.driver.find_element_by_xpath("//input[2]")
        go_button.click()

    def test_error(self):
        raise Exception('some client exception')


class TestEnvironmentVariables(TestCase):
    desired_capabilities = {"environmentVars": {
        "TEST_ENV": "TEST_VALUE",
    }}

    def test_environment_variables(self):
        output = self.vmmaster.run_script("echo $TEST_ENV").get("output")
        self.assertIn(u"TEST_VALUE", output, msg="Not set environment variables in endpoint")


class TestRunScriptOnSessionCreation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desired_capabilities["runScript"] = \
            {"script": 'echo "hello" > ~/hello_file'}
        super(TestRunScriptOnSessionCreation, cls).setUpClass()

    def test_run_script_on_session_creation(self):
        output = self.vmmaster.run_script("cat ~/hello_file").get("output")

        # Virtual machines on origin-ubuntu-16-04 warning message:
        # "/bin/bash: /tmp/**/libtinfo.so.5: no version information available (required by /bin/bash)"
        self.assertIn(u"hello\n", output,
                      msg="%s != %s" % (u"hello\n", output))


def parallel_tests_body(self):
    config = RawConfigParser()
    with open("%s/config" % path, "r") as configfile:
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


def run_scripts_parallel_body(self):
    self.vmmaster.run_script("""
        sudo apt-get update
        sudo apt-get -y install python-pip=1.5.4-1ubuntu3
        pip --version > ~/ver_file
    """)
    output = self.vmmaster.run_script("cat ~/ver_file").get("output")
    self.assertIn(u"pip 1.5.4", output,
                  msg="%s not found in %s" % (u"pip 1.5.4", output))


class TestParallelSlowRunScriptOnSession1(TestCase):
    def test(self):
        run_scripts_parallel_body(self)


class TestParallelSlowRunScriptOnSession2(TestCase):
    def test(self):
        run_scripts_parallel_body(self)


class TestRunScriptWithInstallPackageOnSessionCreation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desired_capabilities["runScript"] = {
            "command": "/bin/bash",
            "script": """
                sudo apt-get update
                sudo apt-get -y install python-pip=1.5.4-1ubuntu3
                pip --version > ~/ver_file
            """}
        super(TestRunScriptWithInstallPackageOnSessionCreation, cls).\
            setUpClass()

    def test_run_script_on_session_creation(self):
        output = self.vmmaster.run_script("cat ~/ver_file").get("output")
        self.assertIn(u"pip 1.5.4", output,
                      msg="%s not found in %s" % (u"pip 1.5.4", output))

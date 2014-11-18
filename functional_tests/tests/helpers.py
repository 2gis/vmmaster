# coding: utf-8
import unittest

from selenium.webdriver import Remote
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from config import config


class TestCase(unittest.TestCase):
    desired_caps = {}

    @classmethod
    def setUpClass(cls):
        if len(cls.desired_caps.items()) == 0:
            cls.desired_caps = DesiredCapabilities.CHROME
        cls.desired_caps["name"] = cls.__name__
        cls.desired_caps["platform"] = config.platform
        cls.desired_caps["takeScreenshot"] = "true"
        cls.driver = Remote(
            command_executor='http://%s:%s/wd/hub' % (config.host, config.port),
            desired_capabilities=cls.desired_caps
        )

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
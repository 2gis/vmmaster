# coding: utf-8
import unittest

from selenium.webdriver import Remote
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from vmmaster_client import vmmaster

from config import config


class TestCase(unittest.TestCase):
    desired_capabilities = None

    def __new__(cls, *args, **kwargs):
        if cls.desired_capabilities is None:
            cls.desired_capabilities = DesiredCapabilities.CHROME.copy()
        cls.desired_capabilities["name"] = cls.__name__

        if hasattr(config, 'platform'):
            cls.desired_capabilities["platform"] = getattr(config, 'platform', 'ANY')

        if hasattr(config, 'browser'):
            cls.desired_capabilities["browserName"] = getattr(config, 'browser', 'ANY')
            if config.browser == 'chrome':
                cls.desired_capabilities["chromeOptions"] = {
                    "args": [
                        "--use-gl",
                        "--ignore-gpu-blacklist"
                    ],
                    "extensions": []
                }

        if hasattr(config, 'version'):
            cls.desired_capabilities["version"] = getattr(config, 'version', 'ANY')

        cls.desired_capabilities["takeScreenshot"] = getattr(config, "take_screenshot", True)
        cls.desired_capabilities["takeScreencast"] = getattr(config, "take_screencast", False)

        token = getattr(config, "token", None)
        cls.desired_capabilities["token"] = token
        return super(TestCase, cls).__new__(cls, *args, **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.driver = Remote(
            command_executor='http://%s:%s/wd/hub' % (config.host, config.port),
            desired_capabilities=cls.desired_capabilities
        )
        cls.vmmaster = vmmaster(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.vmmaster.label(self.__dict__['_testMethodName'])

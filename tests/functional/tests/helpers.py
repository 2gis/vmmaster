# coding: utf-8
import logging
import unittest

from selenium.webdriver import Remote
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from netifaces import ifaddresses, AF_INET
from vmmaster_client import vmmaster
from config import Config


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_microapp_address():
    micro_app_hostname = Config.micro_app_hostname

    def get_address(_interface):
        try:
            return ifaddresses(_interface).setdefault(AF_INET)
        except:
            log.debug("Interface {} wasn't actived.".format(_interface))

    if micro_app_hostname:
        return micro_app_hostname

    for interface in Config.interfaces:
        address_dict = get_address(interface)
        if address_dict:
            return address_dict[0].get("addr", None)


class TestCase(unittest.TestCase):
    platform = None
    desired_capabilities = None

    def __new__(cls, *args, **kwargs):
        if cls.desired_capabilities is None:
            cls.desired_capabilities = DesiredCapabilities.CHROME.copy()
        cls.desired_capabilities["name"] = cls.__name__
        cls.desired_capabilities["platform"] = cls.platform

        if hasattr(Config, 'browser'):
            cls.desired_capabilities["browserName"] = getattr(Config, 'browser', 'ANY')
            if Config.browser == 'chrome':
                cls.desired_capabilities["chromeOptions"] = {
                    "args": [
                        "--use-gl",
                        "--ignore-gpu-blacklist"
                    ],
                    "extensions": []
                }

        if hasattr(Config, 'version'):
            cls.desired_capabilities["version"] = getattr(Config, 'version', 'ANY')

        cls.desired_capabilities["takeScreenshot"] = getattr(Config, "take_screenshot", True)
        cls.desired_capabilities["takeScreencast"] = getattr(Config, "take_screencast", False)

        token = getattr(Config, "token", None)
        cls.desired_capabilities["token"] = token
        return super(TestCase, cls).__new__(cls, *args, **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.driver = Remote(
            command_executor='http://%s:%s/wd/hub' % (Config.host, Config.port),
            desired_capabilities=cls.desired_capabilities
        )
        cls.vmmaster = vmmaster(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.vmmaster.label(self.__dict__['_testMethodName'])

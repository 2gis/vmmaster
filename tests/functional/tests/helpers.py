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
        cls.desired_capabilities["platform"] = config.platform
        cls.desired_capabilities["takeScreenshot"] = "true"
        cls.desired_capabilities["chromeOptions"] = {
            "args": [
                "--use-gl",
                "--ignore-gpu-blacklist"
            ],
            "extensions": []
        }
        cls.desired_capabilities["browser"] = "chrome"
        cls.desired_capabilities["runScript"] = {
            "command": "sudo -S sh",
            "script": "\n        cat <<EOF > /etc/hosts\n        127.0.0.1   localhost\n        127.0.1.1   ubuntu-14-04-x64\n\n        # The following lines are desirable for IPv6 capable hosts\n        ::1     localhost ip6-localhost ip6-loopback\n        ff02::1 ip6-allnodes\n        ff02::2 ip6-allrouters\n\n        # For Online4 func tests\n        \t10.54.25.89\ttile0.maps.2gis.ru\n\t10.54.25.89\ttile1.maps.2gis.ru\n\t10.54.25.89\ttile2.maps.2gis.ru\n\t10.54.25.89\ttile3.maps.2gis.ru\n\t10.54.25.89\ttile4.maps.2gis.ru\n\t10.54.25.89\ttile5.maps.2gis.ru\n\t10.54.25.89\ttile6.maps.2gis.ru\n\t10.54.25.89\ttile8.maps.2gis.ru\n\t10.54.25.89\ttile9.maps.2gis.ru\n\t10.54.25.89\ttile0.maps.2gis.com\n\t10.54.25.89\ttile1.maps.2gis.com\n\t10.54.25.89\ttile2.maps.2gis.com\n\t10.54.25.89\ttile3.maps.2gis.com\n\t10.54.25.89\ttile4.maps.2gis.com\n\t10.54.25.89\ttile5.maps.2gis.com\n\t10.54.25.89\ttile6.maps.2gis.com\n\t10.54.25.89\ttile8.maps.2gis.com\n\t10.54.25.89\ttile9.maps.2gis.com\n\t10.54.25.89\tpubads.g.doubleclick.net\n\t10.54.25.89\tcounter.yadro.ru\n\t10.54.25.89\twww.tns-counter.ru\n\t10.54.25.89\tfront.facetz.net\n\t10.54.25.89\tbs.serving-sys.com\n        EOF\n        "
        }
        cls.desired_capabilities["takeScreencast"] = "true"
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
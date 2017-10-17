# coding: utf-8

from mock import Mock

from tests.helpers import BaseTestCase
from vmmaster.matcher import SeleniumMatcher, PlatformsBasedMatcher


class TestSeleniumMatcherNegative(BaseTestCase):
    def test_empty_platforms_config(self):
        matcher = SeleniumMatcher(platforms={})

        dc = {
            'browserName': 'ANY',
            'version': 'ANY',
            'platform': 'ANY',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))

    def test_any_linux_no_platforms(self):
        matcher = SeleniumMatcher(platforms={'LINUX': {}})

        dc = {
            'platform': 'Linux',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))

    def test_any_linux_no_browser(self):
        matcher = SeleniumMatcher(platforms={'LINUX': {'some_ubuntu': {}}})

        dc = {
            'platform': 'Linux',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))


class TestSeleniumMatcherPositive(BaseTestCase):
    def setUp(self):
        self.matcher = SeleniumMatcher(
            platforms={
                'LINUX': {
                    'ubuntu_1': {
                        'browsers': {'chrome': '58.333'}
                    },
                    'ubuntu_2': {
                        'browsers': {'chrome': '58.222', 'firefox': '10'}
                    },
                    'ubuntu_3': {},
                }
            }
        )

    def test_no_platform_chrome(self):
        dc = {
            'browserName': 'chrome',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_any_platform_chrome(self):
        dc = {
            'platform': 'ANY',
            'browserName': 'chrome',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_any_platform_chrome_with_ver(self):
        dc = {
            'platform': 'ANY',
            'browserName': 'chrome',
            'version': '58'
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_any_platform_chrome_with_full_ver(self):
        dc = {
            'platform': 'ANY',
            'browserName': 'chrome',
            'version': '58.333'
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1'], self.matcher.get_matched_platforms(dc))

    def test_linux_chrome_without_version(self):
        dc = {
            'platform': 'linux',
            'browserName': 'chrome',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_linux_chrome_any_version(self):
        dc = {
            'platform': 'linux',
            'browserName': 'chrome',
            'version': 'ANY',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_linux_firefox_with_version(self):
        dc = {
            'platform': 'linux',
            'browserName': 'firefox',
            'version': '10',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_2'], self.matcher.get_matched_platforms(dc))

    def test_few_matched_platforms(self):
        dc = {
            'platform': 'linux',
            'browserName': 'chrome',
            'version': '58',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))


class TestMatcherFallback(BaseTestCase):
    def test_origin_ubuntu_14(self):
        platforms = {'ubuntu-14.04-x64': Mock()}
        dc = {'platform': 'ubuntu-14.04-x64'}
        matcher = SeleniumMatcher(platforms={}, fallback_matcher=PlatformsBasedMatcher(platforms))

        self.assertTrue(matcher.match(dc))
        self.assertListEqual(['ubuntu-14.04-x64'], matcher.get_matched_platforms(dc))

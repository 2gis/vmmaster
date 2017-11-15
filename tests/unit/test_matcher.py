# coding: utf-8

from mock import Mock, patch
from lode_runner import dataprovider
from tests.helpers import BaseTestCase


class TestSeleniumMatcherNegative(BaseTestCase):
    def test_empty_platforms_config(self):
        from vmmaster.matcher import SeleniumMatcher
        matcher = SeleniumMatcher(platforms={})

        dc = {
            'browserName': 'ANY',
            'version': 'ANY',
            'platform': 'ANY',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))

    def test_any_linux_no_platforms(self):
        from vmmaster.matcher import SeleniumMatcher
        matcher = SeleniumMatcher(platforms={'LINUX': {}})

        dc = {
            'platform': 'Linux',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))

    def test_any_linux_no_browser(self):
        from vmmaster.matcher import SeleniumMatcher
        matcher = SeleniumMatcher(platforms={'LINUX': {'some_ubuntu': {}}})

        dc = {
            'platform': 'Linux',
        }
        self.assertFalse(matcher.match(dc))
        self.assertEqual([], matcher.get_matched_platforms(dc))


class TestSeleniumMatcherPositive(BaseTestCase):
    def setUp(self):
        from vmmaster.matcher import SeleniumMatcher
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
                },
                'WINDOWS': {
                    'win_1': {
                        'browsers': {'internet explorer': '11.0.9600.16384'}
                    },
                    'win_2': {
                        'browsers': {'internet explorer': '9.0.8112.16421'}
                    },
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

    def test_browser_with_partial_ver(self):
        dc = {
            'platform': 'ANY',
            'browserName': 'internet explorer',
            'version': '9'
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['win_2'], self.matcher.get_matched_platforms(dc))

    def test_linux_chrome_without_version(self):
        dc = {
            'platform': 'linux',
            'browserName': 'chrome',
        }
        self.assertTrue(self.matcher.match(dc))
        self.assertListEqual(['ubuntu_1', 'ubuntu_2'], sorted(self.matcher.get_matched_platforms(dc)))

    def test_linux_chrome_empty_version(self):
        dc = {
            'platform': 'linux',
            'browserName': 'chrome',
            'version': '',
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

    def test_any_platform_with_empty_browser(self):
        dc = {
            'platform': 'ANY',
            'browserName': '',
        }
        self.assertFalse(self.matcher.match(dc))
        self.assertListEqual([], self.matcher.get_matched_platforms(dc))


class TestMatcherFallback(BaseTestCase):
    def test_origin_ubuntu_14(self):
        from vmmaster.matcher import SeleniumMatcher, PlatformsBasedMatcher
        platforms = {'ubuntu-14.04-x64': Mock()}
        dc = {'platform': 'ubuntu-14.04-x64'}
        matcher = SeleniumMatcher(platforms={}, fallback_matcher=PlatformsBasedMatcher(platforms))

        self.assertTrue(matcher.match(dc))
        self.assertListEqual(['ubuntu-14.04-x64'], matcher.get_matched_platforms(dc))


def provider(uid, max_limit):
    _provider = Mock()
    type(_provider).id = uid
    type(_provider).max_limit = max_limit
    type(_provider).config = {"LINUX": {"ubuntu_1"}}
    return _provider


class TestMatchingAndBalancing(BaseTestCase):

    @dataprovider([
        (1, 1, [], None, None),
        (0, 1, ["ubuntu_1"], None, None),
        (1, 1, ["ubuntu_1"], "ubuntu_1", 1),
    ])
    def test_matched_platforms_single_provider(self, max_limit, provider_id, platforms, exp_platform, exp_provider):
        with patch(
            'core.sessions.Sessions', Mock()
        ), patch.multiple(
            'vmmaster.app.Vmmaster', get_provider_id=Mock(return_value=provider_id), providers=[provider(1, max_limit)]
        ), patch(
            'vmmaster.matcher.SeleniumMatcher.get_matched_platforms', Mock(return_value=platforms)
        ), patch(
            'core.db.Database', Mock()
        ):
            from vmmaster.app import Vmmaster
            vmmaster = Vmmaster("test")
            platform, provider_id = vmmaster.get_matched_platforms({})

            self.assertEqual(provider_id, exp_provider)
            self.assertEqual(platform, exp_platform)

    @dataprovider([
        ([], ([], []), None, None),
        ((provider(1, 1), provider(2, 1)), ([], []), None, None),
        ((provider(1, 0), provider(2, 0)), (["ubuntu_1"], ["ubuntu_1"]), None, None),
        ((provider(1, 1), provider(2, 1)), ([], ["ubuntu_1"]), "ubuntu_1", 2),
    ])
    def test_matched_platforms_multiple_provider(self, providers, platforms, exp_platform, exp_provider):
        with patch(
            'core.sessions.Sessions', Mock()
        ), patch.multiple(
            'vmmaster.app.Vmmaster', get_provider_id=Mock(return_value=exp_provider), providers=providers
        ), patch(
            'vmmaster.matcher.SeleniumMatcher.get_matched_platforms', Mock(side_effect=platforms)
        ), patch(
            'core.db.Database', Mock()
        ):
            from vmmaster.app import Vmmaster
            vmmaster = Vmmaster("test")
            platform, provider_id = vmmaster.get_matched_platforms({})

            self.assertEqual(provider_id, exp_provider)
            self.assertEqual(platform, exp_platform)

    @dataprovider([
        ({1: 1}, [], 1),
        ({1: 2}, [Mock()], 1),
        ({1: 1}, [Mock()], 1),
        ({1: 1}, [Mock(), Mock()], 1),
    ])
    def test_getting_single_provider(self, limits, active_sessions, expected):
        with patch(
            'core.sessions.Sessions', Mock(active=Mock(return_value=active_sessions))
        ) as sessions, patch(
            'core.db.Database', Mock()
        ):
            from vmmaster.app import Vmmaster
            vmmaster = Vmmaster("test")
            vmmaster.sessions = sessions
            provider_id = vmmaster.get_provider_id(limits)

            self.assertEqual(provider_id, expected)

    @dataprovider([
        ({1: 1, 2: 1}, ([], []), 1),
        ({1: 1, 2: 2}, ([], []), 2),
        ({1: 1, 2: 1}, ([Mock()], []), 2),
        ({1: 1, 2: 1}, ([], [Mock(), Mock()]), 1),
        ({1: 1, 2: 1}, ([Mock(), Mock()], [Mock()]), 2),
        ({1: 1, 2: 2}, ([Mock(), Mock()], [Mock()]), 2),
        ({1: 2, 2: 2}, ([Mock(), Mock()], [Mock(), Mock()]), 1),
    ])
    def test_getting_multiple_providers(self, limits, active_sessions, expected):
        with patch(
                'core.sessions.Sessions', Mock(active=Mock(side_effect=active_sessions))
        ) as sessions, patch(
            'core.db.Database', Mock()
        ):
            from vmmaster.app import Vmmaster
            vmmaster = Vmmaster("test")
            vmmaster.sessions = sessions
            provider_id = vmmaster.get_provider_id(limits)

            self.assertEqual(provider_id, expected)

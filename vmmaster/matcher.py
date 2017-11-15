# -*- coding: utf-8 -*-

import logging
from core import constants

log = logging.getLogger(__name__)


class IMatcher(object):
    def get_matched_platforms(self, platform):
        """
        Return all matched platforms available
        :param platform: str
        :return: list of str
        """
        raise NotImplemented

    def match(self, dc):
        """
        Main matcher method, must return True/False
        :param dc: desired capabilities dictionary
        :return: boolean
        """
        raise NotImplemented


class PlatformsBasedMatcher(IMatcher):
    def __init__(self, platforms):
        self.platforms = platforms

    def get_matched_platforms(self, platform):
        if platform == constants.ANY:
            return self.platforms.keys()

        platform = platform.lower()
        if platform in self.platforms.keys():
            return [platform]

        return []

    def match(self, dc):
        platform = dc.get('platform', constants.ANY)
        return bool(self.get_matched_platforms(platform))


class SeleniumMatcher(IMatcher):
    def __init__(self, platforms=None, fallback_matcher=None):
        """
        :param platforms: list of platforms configuration
        :param fallback_matcher: object with IMatcher interface
        """
        self.platforms = {k.upper(): v for k, v in platforms.items()} if platforms else {}
        self.fallback = fallback_matcher

    def _filter_platforms_by_platform_type(self, desired_platform):
        """
        Find all matched platforms available
        :param desired_platform: str name
        :return: dict
        """
        if desired_platform == constants.ANY:
            all_platforms = {}
            for platform in self.platforms.keys():
                all_platforms.update(self._filter_platforms_by_platform_type(platform))
            return all_platforms

        if desired_platform in self.platforms.keys():
            return self.platforms[desired_platform]

        return {}

    def _match_browser_version(self, desired_version, version):
        """
        Match browser version
        :param desired_version: str
        :param version: str
        :return: boolean
        """
        if desired_version == constants.ANY:
            return True
        elif version == desired_version:
            log.debug('Requested browserVersion={}. Full match found'.format(desired_version))
            return True
        elif version.split('.')[0] == desired_version:
            log.debug('Requested browserVersion={}. Matches to {}'.format(desired_version, version))
            return True
        return False

    def _filter_platforms_by_browser_match(self, platforms, desired_browser, desired_version):
        """
        Find all platforms with matched browserName and version installed
        :param platforms: dict with platform names as a keys and lists of browsers as values
               example: {'ubuntu-14': {'browsers': {'chrome': '52'}}}
        :param desired_browser: str
        :param desired_version: str
        :return: list(str)
        """
        matched_platforms = []
        for platform, details in platforms.items():
            browsers = details.get('browsers', {})
            if not browsers:
                log.debug('No browsers found for {}'.format(platform))
                continue

            for browser, version in browsers.items():
                if desired_browser == constants.ANY:
                    matched_platforms.append(platform)
                    continue

                if desired_browser == browser and self._match_browser_version(desired_version, version):
                    matched_platforms.append(platform)

        log.debug("Matched platforms for browserName={} version={} found: {}".format(
            desired_browser, desired_version, matched_platforms)
        )
        return matched_platforms

    def get_matched_platforms(self, dc):
        """
        Find available matched platforms for passed desired capabilities dict. Based on the PLATFORMS config section
        :param dc: Desired Capabilities dictionary
        :return: matched platforms list
        """
        desired_platform_type = dc.get('platform', constants.ANY).upper()
        matched_platforms = self._filter_platforms_by_platform_type(desired_platform_type)
        log.debug("Matched platforms found for dc={}: {}".format(dc, matched_platforms))

        if matched_platforms:
            desired_browser = dc.get('browserName')
            if not desired_browser:
                log.warning('Empty browser in DesiredCapabilities={}. Cannot match'.format(dc))
                return []

            desired_version = dc.get('version') or constants.ANY  # escape empty version
            return self._filter_platforms_by_browser_match(matched_platforms, desired_browser, desired_version)

        if self.fallback:
            log.debug('Using fallback matcher {} for platform {}'.format(
                self.fallback.__class__.__name__, desired_platform_type)
            )
            return self.fallback.get_matched_platforms(desired_platform_type)

        return []

    def match(self, dc):
        return bool(self.get_matched_platforms(dc))

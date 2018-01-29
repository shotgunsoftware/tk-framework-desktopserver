# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pprint

from . import logger

logger = logger.get_logger("settings")


class Settings(object):
    """
    Reads the optionally configured configuration file present in the Desktop
    installer package. This file is in the root of the installed application folder on
    Linux and Windows and in Contents/Resources on MacOSX.

    The configuration file should have the following format:
    [BrowserIntegration]
    port=9000
    debug=1
    certificate_folder=/path/to/the/certificate
    """

    _DEFAULT_PORT = 9000

    _BROWSER_INTEGRATION = "BrowserIntegration"
    _PORT_SETTING = "port"
    _CERTIFICATE_FOLDER_SETTING = "certificate_folder"
    _ENABLED = "enabled"
    _HOST_ALIASES = "HostAliases"

    def __init__(self, default_certificate_folder):
        """
        Constructor.

        If the configuration file doesn't not exist, the configuration
        object will return the default values.

        :param default_certificate_folder: Default location for the certificate file. This value
            is overridable for each app that can use this settings object.
        """

        self._default_certificate_folder = default_certificate_folder

        from sgtk.util import UserSettings
        user_settings = UserSettings()
        port = user_settings.get_integer_setting(
            self._BROWSER_INTEGRATION, self._PORT_SETTING
        )
        certificate_folder = user_settings.get_setting(
            self._BROWSER_INTEGRATION, self._CERTIFICATE_FOLDER_SETTING
        )
        integration_enabled = UserSettings().get_boolean_setting(self._BROWSER_INTEGRATION, self._ENABLED)

        raw_host_aliases = {}
        if UserSettings().get_section_settings(self._HOST_ALIASES):
            raw_host_aliases = {
                name: UserSettings().get_setting(
                    self._HOST_ALIASES, name
                )
                for name in UserSettings().get_section_settings(self._HOST_ALIASES)
            }

        self._port = port or self._DEFAULT_PORT
        self._certificate_folder = certificate_folder or self._default_certificate_folder
        self._integration_enabled = integration_enabled

        # Keep the raw aliases for support, but filter the settings for API users.
        self._raw_host_aliases = raw_host_aliases
        self._host_aliases = {}
        # Ensure we have a string, and then split the string on commas, make sure we're stripping
        # out beginning and end of string whitespaces and then lowercase everything.
        # Also skip empty tokens.
        for main_host, secondary_hosts in raw_host_aliases.iteritems():
            main_host = main_host.strip().lower()
            # Skip empty hosts.
            if not main_host:
                continue

            self._host_aliases[main_host] = [
                secondary_host.lower().strip()
                for secondary_host in secondary_hosts.split(",")
            ]

    @property
    def port(self):
        """
        The port to listen on for incoming websocket requests.
        """
        return self._port

    @property
    def integration_enabled(self):
        """
        Flag indicating if the browser integration is enabled. ``True`` if enabled, ``False`` if not.
        """
        return self._integration_enabled if self._integration_enabled is not None else True

    @property
    def certificate_folder(self):
        """
        Path to the self-signed certificates folder.
        """
        return self._certificate_folder

    @property
    def host_aliases(self):
        """
        Alternative hosts that are allowed to connect to the browser integration.

        This is an expert setting and should only be used when dealing with separate endpoints
        for API access and webapp access.
        """
        return self._host_aliases

    def dump(self, logger):
        """
        Dumps all the settings into the logger.
        """
        logger.debug("Integration enabled: %s" % self.integration_enabled)
        logger.debug("Certificate folder: %s" % self.certificate_folder)
        logger.debug("Port: %d" % self.port)
        logger.debug("Host aliases: %s" % pprint.pformat(self._raw_host_aliases))

# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
from mock import Mock

from base_test import TestDesktopServerFramework
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, SealedMock

import sgtk

# Mock Qt since we don't have it.
sgtk.platform.qt.QtCore = Mock()
sgtk.platform.qt.QtGui = Mock()

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(repo_root, "python"))

from tk_framework_desktopserver import Settings


class TestFrameworkWithUserSettings(ShotgunTestBase):
    """
    Tests that the Settings objects works properly.
    """

    def test_default_browser_integration_settings(self):
        """
        Make sure browser integrations settings have good default values.
        """
        settings = Settings(None)
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.certificate_folder, None)
        self.assertEqual(settings.integration_enabled, True)
        self.assertDictEqual(settings.host_aliases, {})

    def test_browser_integration_settings(self):
        """
        Makes sure browser integration settings are read properly from disk.
        """
        self.write_toolkit_ini_file(
            BrowserIntegration={
                "port": 9001,
                "certificate_folder": "/a/b/c",
                "enabled": False,
            }
        )

        settings = Settings(None)
        self.assertEqual(settings.port, 9001)
        self.assertEqual(settings.certificate_folder, "/a/b/c")
        self.assertEqual(settings.integration_enabled, False)

    def test_host_aliases(self):
        """
        Make sure the settings are filtered correctly.
        """
        self.write_toolkit_ini_file(
            HostAliases={
                "site.with.spaces.AND.CAPS ": " alt.site.with.spaces.AND.CAPS, another.alt.site.with.spaces.AND.CAPS ",
                "site.without.aliases": "",
            }
        )

        settings = Settings(None)

        # Make sure spaces and caps have been removed, as well as empty entries.
        self.assertDictEqual(
            settings.host_aliases,
            {
                "site.with.spaces.and.caps": [
                    "alt.site.with.spaces.and.caps",
                    "another.alt.site.with.spaces.and.caps",
                ],
                "site.without.aliases": [""],
            },
        )


class TestAliasesLookup(TestDesktopServerFramework):
    def test_host_aliases_parsing(self):
        """
        Tests that the aliases list generated from the alias dict is generated as intended.
        """
        self.framework._settings = SealedMock(
            host_aliases={"www.site.com": ["alt.site.com"]}
        )

        for site in [
            "https://alt.site.com",
            "https://www.site.com",
            "https://alt.site.com:8888",
            "https://www.site.com:8888",
        ]:

            self.assertEqual(
                self.framework._get_host_aliases(site), ["www.site.com", "alt.site.com"]
            )

        self.assertEqual(
            self.framework._get_host_aliases("https://www.unknown.site.com"),
            ["www.unknown.site.com"],
        )

import os
import sys
from mock import Mock

from base_test import TestDesktopServerFramework
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import ShotgunTestBase, SealedMock

import sgtk
# Mock Qt since we don't have it.
sgtk.platform.qt.QtCore = Mock()
sgtk.platform.qt.QtGui = Mock()

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(repo_root, "python"))

from tk_framework_desktopserver import Settings


class TestFrameworkWithUserSettings(ShotgunTestBase):

    def test_no_host_aliases_section(self):
        """
        Make sure empty settings file is reported an empty.
        """
        settings = Settings(None)
        self.assertDictEqual(settings.host_aliases, {})

    def test_filtered_aliases(self):
        """
        Make sure the settings are filtered correctly.
        """
        self.write_toolkit_ini_file(
            HostAliases={
                "site.with.spaces.AND.CAPS ":
                    " alt.site.with.spaces.AND.CAPS, another.alt.site.with.spaces.AND.CAPS ",
                "site.without.aliases": ""
            }
        )

        settings = Settings(None)

        # Make sure spaces and caps have been removed, as well as empty entries.
        self.assertDictEqual(
            settings.host_aliases,
            {
                "site.with.spaces.and.caps": [
                    "alt.site.with.spaces.and.caps",
                    "another.alt.site.with.spaces.and.caps"
                ],
                "site.without.aliases": [""]
            }
        )


class TestAliasesLookup(TestDesktopServerFramework):

    def test_host_aliases_parsing(self):

        self.framework._settings = SealedMock(
            host_aliases={
                "www.site.com": ["alt.site.com"]
            }
        )

        for site in ["https://alt.site.com", "https://www.site.com",
                     "https://alt.site.com:8888", "https://www.site.com:8888"]:

            self.assertEqual(
                self.framework._get_host_aliases(site),
                ["www.site.com", "alt.site.com"]
            )

        self.assertEqual(
            self.framework._get_host_aliases("https://www.unknown.site.com"),
            ["www.unknown.site.com"]
        )

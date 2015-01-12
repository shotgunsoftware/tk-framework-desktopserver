# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import subprocess

from Cocoa import NSOpenPanel, NSOKButton

from process_manager import ProcessManager

class ProcessManagerMac(ProcessManager):
    """
    Mac OS Interface for Shotgun Commands.
    """

    def platform_name(self):
        return "mac"

    def open(self, filepath):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        """
        self._verify_file_open(filepath)
        launcher = self._get_launcher()

        if launcher is None:
            launcher = "open"

        return self._launch_process([launcher, filepath], "Could not open file.")

    def pick_file_or_directory(self, multi=False):
        """
        Pop-up a file selection window.

        :param multi: Boolean Allow selecting multiple elements.
        :returns: List of files that were selected with file browser.
        """
        panel = NSOpenPanel.openPanel()

        panel.setAllowsMultipleSelection_(multi)
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(True)
        panel.setResolvesAliases_(False)

        result = panel.runModal()

        files = []
        if result == NSOKButton:
            filesToOpen = panel.filenames()
            for f in filesToOpen:
                out = f
                if os.path.isdir(f):
                    out += "/"

                files.append(out)

        return files

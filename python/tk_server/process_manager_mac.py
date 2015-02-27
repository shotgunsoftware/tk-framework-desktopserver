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
from threading import Timer

from Cocoa import NSOpenPanel, NSOKButton, NSRunningApplication, NSApplicationActivateIgnoringOtherApps

from process_manager import ProcessManager

class ProcessManagerMac(ProcessManager):
    """
    Mac OS Interface for Shotgun Commands.
    """

    platform_name = "mac"

    def _bring_panel_to_front(self, panel):
        """
        Brings given panel to front of all windows.
        Used to bring a dialog to the user's attention.

        :param panel: Panel to bring to front
        """

        # Brings the application to the front
        NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

        # Brings the panel to the front
        panel.orderFrontRegardless()

    def open(self, filepath):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        :returns: Bool If the operation was successful
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

        # Needs to bring the panel to the front after it has been drawn, otherwise getting an error regarding
        # operation can not happen while updating cell rows.
        timer = Timer(0.1, self._bring_panel_to_front, panel)
        timer.start()

        result = panel.runModal()

        files = []
        if result == NSOKButton:
            files_to_open = panel.filenames()
            for f in files_to_open:
                out = f
                if os.path.isdir(f):
                    out += os.path.sep

                files.append(out)

        return files

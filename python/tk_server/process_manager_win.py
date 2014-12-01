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

from process_manager import ProcessManager

class ProcessManagerWin(ProcessManager):
    """
    Windows OS Interface for Shotgun Commands.
    """
    def _get_toolkit_script_name(self):
        return "shotgun.bat"

    def _get_toolkit_fallback_script_name(self):
        return "tank.bat"

    def open(self, filepath):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        """
        self._verify_file_open(filepath)
        launcher = self._get_launcher()

        if launcher is None:
            # Note: startfile is always async.
            os.startfile(filepath)
        else:
            # Note: Using Popen install of call for asynchronous behavior
            subprocess.Popen([launcher, filepath])

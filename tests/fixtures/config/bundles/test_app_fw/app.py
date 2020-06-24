# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
A dummy app that is used to load certain frameworks and has commands that write the command name in a
file for testing
"""
import os

from sgtk.platform import Application


class TestAppFW(Application):
    def store_string_in_file(self, value):
        """
        Returns a function that the commands use as their callback in order to write a string (the command name) into
        a file for testing. The file path is taken from the environment variable TK_FW_DESKTOP_SERVER_TEST_FILE_PATH
        """

        def func():
            with open(os.environ["TK_FW_DESKTOP_SERVER_TEST_FILE_PATH"], "w") as f:
                f.write(value)

        return func

    def init_app(self):
        self.engine.register_command(
            "Command A", self.store_string_in_file("Command A")
        )
        self.engine.register_command(
            "Command B", self.store_string_in_file("Command B")
        )

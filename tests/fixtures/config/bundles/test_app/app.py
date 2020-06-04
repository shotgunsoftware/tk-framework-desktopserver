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
A dummy app
"""
import os

from sgtk.platform import Application


class TestApp(Application):
    def store_string_in_file(self, command_name):
        def func():
            with open(os.environ["TK_FW_DESKTOP_SERVER_TEST_FILE_PATH"], "w") as f:
                f.write(command_name)

        return func

    def init_app(self):
        self.engine.register_command(
            "Command A", self.store_string_in_file("Command A")
        )
        self.engine.register_command(
            "Command B", self.store_string_in_file("Command B")
        )

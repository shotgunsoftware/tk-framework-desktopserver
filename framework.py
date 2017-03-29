# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import os
import struct
from sgtk.util import LocalFileStorageManager


class DesktopserverFramework(sgtk.platform.Framework):

    ##########################################################################################
    # init and destroy
    def init_framework(self):
        self._server = None
        self._settings = None

    def init_desktop_server(self):

        tk_framework_desktopserver = self.import_module("tk_framework_desktopserver")
        self._settings = tk_framework_desktopserver.Settings(
            location=None, # Passing in None will have the desktop user use the UserSettings API instead of reading a file.
            default_certificate_folder=os.path.join(
                LocalFileStorageManager.get_global_root(
                    LocalFileStorageManager.CACHE, LocalFileStorageManager.CORE_V18
                ),
                "desktop",
                "config",
                "certificates"
            )
        )

        self._settings.dump(self.logger)

        if self.__is_64bit_python() and self._settings.integration_enabled:
            return

        self._server = tk_framework_desktopserver.Server(
            port=self._settings.port,
            low_level_debug=self._settings.low_level_debug,
            whitelist=self._settings.whitelist,
            keys_path=self._settings.certificate_folder
        )

        try:
            self._server.start()
        except tk_framework_desktopserver.PortBusyError:
            logger.exception("Could not start the browser integration:")
            # TODO: Do we ask the user if he wants to quit?

    def destroy_framework(self):
        if not self._server and self._server.is_running():
            server.tear_down()

    def __is_64bit_python(self):
        """
        :returns: True if 64-bit Python, False otherwise.
        """
        return struct.calcsize("P") == 8

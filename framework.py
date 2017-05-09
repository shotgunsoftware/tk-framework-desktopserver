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
import sys
import os
import struct
from sgtk.util import LocalFileStorageManager


class DesktopserverFramework(sgtk.platform.Framework):
    """
    Provides browser integration.
    """

    def __init__(self, *args, **kwargs):
        super(DesktopserverFramework, self).__init__(*args, **kwargs)
        self._server = None
        self._settings = None
        self._tk_framework_desktopserver = None

    def add_different_user_requested_callback(self, cb):
        """
        Registers a callback to know when a different user or site is making browser integration requests.
        The caller is not waiting for the callback to return.

        :param function cb: Callback of the form:
            def callback(site, user_id):
                '''
                Called when the site or user is different than the current site or user.

                :param str site: Url of the site the request is coming from.
                :param int user_id: Id of the HumanUser who made the request.
                '''
        """
        # Lazy-init because engine is initialized after its frameworks, so QtCore is not initialized yet.
        from sgtk.platform.qt import QtCore
        if self._server:
            self._server.notifier.different_user_requested.connect(cb, type=QtCore.Qt.QueuedConnection)

    ##########################################################################################
    # init and destroy
    def launch_desktop_server(self, host, user_id):
        """
        Initializes the desktop server.

        The server actually supports two protocols, named v1 and v2. v1 can be used to process requests from any
        users from any sites, while v2 can only be used to process requests from the currently authenticated
        user.

        :param str host: Host for which we desire to answer requests.
        :param int user_id: Id of the user for which we desire to answer requests.
        """
        self._tk_framework_desktopserver = self.import_module("tk_framework_desktopserver")

        # Read the browser integration settings from disk. By passing in location=None, the Toolkit API will be
        # used to locate the settings instead of looking at a specific file.
        self._settings = self._tk_framework_desktopserver.Settings(
            location=None,
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

        # Twisted only runs on 64-bits.
        if not self.__is_64bit_python():
            self.logger.warning("The browser integration is only available with 64-bit versions of Python.")
            self._integration_enabled = False
        # Did the user disable it?
        elif not self._settings.integration_enabled:
            self.logger.info("Browser integration has been disabled in the Toolkit settings.")
            self._integration_enabled = False
        else:
            self._integration_enabled = True

        if not self._integration_enabled:
            return

        try:
            self.__ensure_certificate_ready()

            self._server = self._tk_framework_desktopserver.Server(
                keys_path=self._settings.certificate_folder,
                host=host,
                user_id=user_id,
                low_level_debug=self._settings.low_level_debug,
                port=self._settings.port
            )

            self._server.start()
        except Exception:
            self.logger.exception("Could not start the browser integration:")

    def destroy_framework(self):
        """
        Called on finalization of the framework.

        Closes the websocket server.
        """
        if self._server and self._server.is_running():
            self._server.tear_down()

    def __ensure_certificate_ready(self):
        """
        Ensures that the certificates are created and registered. If something is amiss, then the
        certificates are regenerated.
        """
        cert_handler = self._tk_framework_desktopserver.get_certificate_handler(
            self._settings.certificate_folder
        )

        # We only warn once.
        warned = False
        # Make sure the certificates exist.
        if not cert_handler.exists():
            self.logger.info("Certificate doesn't exist.")
            # Start by unregistering certificates from the keychains, this can happen if the user
            # wiped his shotgun/desktop/config/certificates folder.
            if cert_handler.is_registered():
                self.logger.info("Unregistering lingering certificate.")
                # Warn once.
                self.__warn_for_prompt()
                warned = True
                cert_handler.unregister()
                self.logger.info("Unregistered.")
            # Create the certificate files
            cert_handler.create()
            self.logger.info("Certificate created.")
        else:
            self.logger.info("Certificate already exist.")

        # Check if the certificates are registered with the keychain.
        if not cert_handler.is_registered():
            self.logger.info("Certificate not registered.")

            # Only if we've never been warned before.
            if not warned:
                self.__warn_for_prompt()
            cert_handler.register()
            self.logger.info("Certificate registered.")
        else:
            self.logger.info("Certificates already registered.")

    def __get_certificate_prompt(self, keychain_name, action):
        """
        Generates the text to use when alerting the user that we need to register the certificate.

        :param keychain_name: Name of the keychain-like entity for a particular OS.
        :param action: Description of what the user will need to do when the OS prompts the user.

        :returns: String containing an error message formatted
        """
        return ("The Shotgun Desktop needs to update the security certificate list from your %s before "
                "it can turn on the browser integration.\n"
                "%s" % (keychain_name, action))

    def __warn_for_prompt(self):
        """
        Warn the user he will be prompted.
        """
        from sgtk.platform.qt import QtGui

        if sys.platform == "darwin":
            QtGui.QMessageBox.information(
                None,
                "Shotgun browser integration",
                self.__get_certificate_prompt(
                    "keychain",
                    "You will be prompted to enter your username and password by MacOS's keychain "
                    "manager in order to proceed with the updates."
                )
            )
        elif sys.platform == "win32":
            QtGui.QMessageBox.information(
                None,
                "Shotgun browser integration",
                self.__get_certificate_prompt(
                    "Windows certificate store",
                    "Windows will now prompt you to accept one or more updates to your certificate store."
                )
            )
        # On Linux there's no need to prompt. It's all silent.

    def __is_64bit_python(self):
        """
        :returns: True if 64-bit Python, False otherwise.
        """
        return struct.calcsize("P") == 8

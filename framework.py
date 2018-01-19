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
import urlparse
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

    def can_run_server(self):
        """
        Checks if we can use the framework to run the server.

        :returns: ``True`` if we can, ``False`` otherwise.
        """
        # Server requires 64-bit libraries to run.
        return self.__is_64bit_python()

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
    def launch_desktop_server(self, host, user_id, parent=None):
        """
        Initializes the desktop server.

        The server actually supports two protocols, named v1 and v2. v1 can be used to process requests from any
        users from any sites, while v2 can only be used to process requests from the currently authenticated
        user.

        :param str host: Host for which we desire to answer requests.
        :param int user_id: Id of the user for which we desire to answer requests.
        :param parent: Parent widget for any pop-ups to show during initialization.
        :type parent: :class:`PySide.QtGui.QWidget`
        """
        # Twisted only runs on 64-bits.
        # No not even attempt to import the framework, as it will cause 64-bits DLLs to be loaded.
        if not self.__is_64bit_python():
            self.logger.warning("The browser integration is only available with 64-bit versions of Python.")
            self._integration_enabled = False
            return

        self._tk_framework_desktopserver = self.import_module("tk_framework_desktopserver")

        # Read the browser integration settings from disk. By passing in location=None, the Toolkit API will be
        # used to locate the settings instead of looking at a specific file.
        self._settings = self._tk_framework_desktopserver.Settings(
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

        # Did the user disable it?
        if not self._settings.integration_enabled:
            self.logger.info("Browser integration has been disabled in the Toolkit settings.")
            self._integration_enabled = False
        else:
            self._integration_enabled = True

        if not self._integration_enabled:
            return

        try:
            if self._site_supports_shotgunlocalhost():
                self.__retrieve_certificates_from_shotgun()
                keys_path = self._get_shotgunlocalhost_keys_folder()
                encrypt = True
            else:
                self.__ensure_certificate_ready(regenerate_certs=False, parent=parent)
                keys_path = self._settings.certificate_folder
                encrypt = False

            self._server = self._tk_framework_desktopserver.Server(
                keys_path=keys_path,
                encrypt=encrypt,
                host=host,
                user_id=user_id,
                host_aliases=self._get_host_aliases(host),
                port=self._settings.port
            )

            self._server.start()
        except Exception:
            self.logger.exception("Could not start the browser integration:")

    def _get_shotgunlocalhost_keys_folder(self):
        """
        Retrieves the location where the shotgunlocalhost.com keys will be downloaded to.

        :returns: Path to the folder where server.crt and server.key are.
        """
        return os.path.join(self.cache_location, "keys")

    def _get_host_aliases(self, host):
        """
        Returns a list of valid hosts that can connect to the browser integration. The returned
        list only contains the hostname. The port number and protocol are removed.

        :returns: List of hostnames.
        """
        self.logger.debug("Looking for an alias for host %s.", host)
        # parse the host and keep only the network location, no need for the rest.
        parsed_host = urlparse.urlparse(host)
        # When the network location has a port number, the hostname and port
        # members are not None, in which case we want just the hostname and don't
        # care about the port number. If hostname is not set, then we can grab
        # the network location safely.
        hostname = (parsed_host.hostname or parsed_host.netloc).lower()
        self.logger.debug("Hostname is %s.", hostname)

        # Return the dictionary into a list of pool of aliases. Each list is
        # a different site. If one of the pool has the current site, we'll
        # return that pool.
        aliases = [
            [main_host] + alt_hosts
            for main_host, alt_hosts in self._settings.host_aliases.iteritems()
        ]

        # If we don't have any aliases in the file.
        if not aliases:
            self.logger.debug("No host aliases found in settings. '%s' will be used.", hostname)
            return [hostname]

        for aliases_pool in aliases:
            if hostname in aliases_pool:
                self.logger.debug("Host aliases were found. '%s' will be used", ",".join(aliases_pool))
                return aliases_pool

        self.logger.debug("There are no host aliases for this host. '%s' will be used.", hostname)
        return [hostname]

    def _write_cert(self, filename, cert):
        """
        Writes a certificate to disk. Converts any textual \n into actual \n. This is required
        because certificates returned from Shotgun have their \n encoded as actual \n in the text.

        :param filename: Name of the file to save under the keys folder.
        :param cert: Certificate taken from Shotgun.
        """
        with open(os.path.join(self._get_shotgunlocalhost_keys_folder(), filename), "w") as fw:
            fw.write("\n".join(cert.split("\\n")))

    def _site_supports_shotgunlocalhost(self):
        """
        Checks if the site supports encryption.
        """
        return self.shotgun.server_info.get("shotgunlocalhost_browser_integration_enabled", False)

    def can_regenerate_certificates(self):
        """
        Indicates if we can regenerate certificates.

        Certificates can only be regenerated when we're not using shotgunlocalhost.

        :returns: True if certificates can be regenerated, False otherwise.
        """
        return self._site_supports_shotgunlocalhost() is False

    def regenerate_certificates(self, parent=None):
        """
        Regenerates the certificates.

        :param parent: Parent widget for any pop-ups to show during certificate generation.
        :type parent: :class:`PySide.QtGui.QWidget`
        """
        self.__ensure_certificate_ready(regenerate_certs=True, parent=parent)

    def destroy_framework(self):
        """
        Called on finalization of the framework.

        Closes the websocket server.
        """
        if self._server and self._server.is_running():
            self._server.tear_down()

    def __retrieve_certificates_from_shotgun(self):
        """
        Retrieves certificates from Shotgun.
        """
        self.logger.debug("Retrieving certificates from Shotgun")
        certs = self.shotgun._call_rpc("sg_desktop_certificates", {})
        sgtk.util.filesystem.ensure_folder_exists(self._get_shotgunlocalhost_keys_folder())
        if not certs["sg_desktop_cert"]:
            self.logger.error(
                "shotgunlocalhost.com public key is not set in Shotgun. "
                "Please contact support@shotgunsoftware.com"
            )
        else:
            self._write_cert("server.crt", certs["sg_desktop_cert"])

        if not certs["sg_desktop_key"]:
            self.logger.error(
                "shotgunlocalhost.com private key is not set in Shotgun. "
                "Please contact support@shotgunsoftware.com"
            )
        else:
            self._write_cert("server.key", certs["sg_desktop_key"])

    def __ensure_certificate_ready(self, regenerate_certs=False, parent=None):
        """
        Ensures that the certificates are created and registered. If something is amiss, then the
        certificates are regenerated.

        :param bool regenerate_certs: If ``True``, certificates will be regenerated.
        :param parent: Parent widget for any pop-ups to show during certificate generation.
        :type parent: :class:`PySide.QtGui.QWidget`
        """
        cert_handler = self._tk_framework_desktopserver.get_certificate_handler(
            self._settings.certificate_folder
        )

        if regenerate_certs:
            self.logger.info("Backing up current certificates files if they exist.")
            cert_handler.backup_files()

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
                self.__warn_for_prompt(parent)
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
                self.__warn_for_prompt(parent)
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
                "\n"
                "%s" % (keychain_name, action))

    def __warn_for_prompt(self, parent):
        """
        Warn the user he will be prompted.
        """
        from sgtk.platform.qt import QtGui

        if sys.platform == "darwin":
            QtGui.QMessageBox.information(
                parent,
                "Shotgun browser integration",
                self.__get_certificate_prompt(
                    "keychain",
                    "You will be prompted to enter your username and password by MacOS's keychain "
                    "manager in order to proceed with the updates."
                )
            )
        elif sys.platform == "win32":
            QtGui.QMessageBox.information(
                parent,
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

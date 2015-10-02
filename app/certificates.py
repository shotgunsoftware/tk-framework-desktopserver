# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import logging
import optparse


def __get_certificate_prompt(keychain_name, action):
    """
    Generates the text to use when alerting the user that we need to register the certificate.

    :param keychain_name: Name of the keychain-like entity for a particular OS.
    :param action: Description of what the user will need to do when the OS prompts the user.

    :returns: String containing an error message formatted
    """
    return ("This script needs to install a security certificate into your %s before "
            "it can turn on the browser integration.\n"
            "%s.\nPress ENTER to continue." % (keychain_name, action))


def __warn_for_prompt():
    """
    Warn the user he will be prompted.
    """
    if sys.platform == "darwin":
        raw_input(
            __get_certificate_prompt(
                "keychain",
                "You will be prompted to enter your username and password by MacOS's keychain "
                "manager in order to proceed with the update."
            )
        )
    elif sys.platform == "win32":
        raw_input(
            __get_certificate_prompt(
                "Windows certificate store",
                "Windows will now prompt you to accept an update to your certificate store."
            )
        )
    # On Linux there's no need to prompt. It's all silent.


def __remove_certificate(certificate_folder):
    """
    Ensures that the certificates are created and registered. If something is amiss, then the
    configuration is fixed.

    :param certificate_folder: Folder where the certificates are stored.
    """

    cert_handler = tk_framework_desktopserver.get_certificate_handler(certificate_folder)

    # Check if there is a certificate registered with the keychain.
    if cert_handler.is_registered():
        logger.debug("Removing certificate from database.")
        __warn_for_prompt()
        cert_handler.unregister()
        logger.info("The certificate is now unegistered.")
    else:
        logger.info("No certificate was registered.")

    # Make sure the certificates exist.
    if cert_handler.exists():
        logger.debug("Certificate was found on disk at %s." % certificate_folder)
        cert_handler.remove_files()
        logger.info("The certificate was removed at %s." % certificate_folder)
    else:
        logger.info("No certificate was found on disk at %s." % certificate_folder)


def __create_certificate(certificate_folder):
    """
    Ensures that the certificates are created and registered. If something is amiss, then the
    configuration is fixed.

    :param certificate_folder: Folder where the certificates are stored.
    """

    cert_handler = tk_framework_desktopserver.get_certificate_handler(certificate_folder)

    # We only warn once.
    warned = False
    # Make sure the certificates exist.
    if not cert_handler.exists():
        logger.debug("Certificate doesn't exist on disk.")
        # Start by unregistering certificates from the keychains, this can happen if the user
        # wiped his certificates folder.
        if cert_handler.is_registered():
            # Warn once.
            __warn_for_prompt()
            logger.debug("Unregistering dangling certificate from database...")
            warned = True
            cert_handler.unregister()
            logger.debug("Done.")
        # Create the certificate files
        logger.debug("About to create the certificates...")
        cert_handler.create()
        logger.info("Certificate created at %s." % certificate_folder)
    else:
        logger.info("Certificate already exist on disk at %s." % certificate_folder)

    # Check if the certificates are registered with the keychain.
    if not cert_handler.is_registered():
        logger.debug("Certificate is not currently registered in the keychain.")
        # Only if we've never been warned before.
        if not warned:
            __warn_for_prompt()
        cert_handler.register()
        logger.info("Certificate is now registered .")
    else:
        logger.info("Certificate is already registered.")


if __name__ == '__main__':
    # Add the modules files to PYTHOHPATH
    sys.path.insert(0, "../python")
    import tk_framework_desktopserver

    # Make sure logger output goes to stdout
    logger = tk_framework_desktopserver.get_logger()
    logger.addHandler(logging.StreamHandler())

    parser = optparse.OptionParser()
    parser.add_option(
        "--debug", action="store_true", default=False,
        help="prints debugging message from the certificate generation."
    )
    parser.add_option(
        "--remove", action="store_true", default=False,
        help="prints debugging message from the certificate generation."
    )

    options, _ = parser.parse_args()

    if options.debug is True:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    folder = os.environ.get("TANK_BROWSER_INTEGRATION_CERTIFICATE", "../resources/keys")
    folder = os.path.expanduser(folder)
    folder = os.path.abspath(folder)
    folder = os.path.normpath(folder)

    if options.remove:
        __remove_certificate(folder)
    else:
        __create_certificate(folder)

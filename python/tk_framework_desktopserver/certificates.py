# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import os
import sys
import subprocess

from OpenSSL import crypto


def _write_file(path, content):
    """
    Writes text to a file.

    :param path: Path to the file.
    :param content: Text to write to disl.
    """
    old_umask = os.umask(0077)
    try:
        with open(path, "wt") as f:
            f.write(content)
    finally:
        os.umask(old_umask)


def _clean_folder_for_file(filepath):
    """
    Makes sure the folder exists for a given file and that the file doesn't exist.

    :param filepath: Path to the file we want to make sure the parent directory
                     exists.
    """

    folder = os.path.dirname(filepath)
    if not os.path.exists(folder):
        old_umask = os.umask(0077)
        try:
            os.makedirs(folder, 0700)
        finally:
            os.umask(old_umask)
    if os.path.exists(filepath):
        os.remove(filepath)


def create_self_signed_cert(cert_path, key_path):
    """
    Creates a self-signed certificate.

    :param cert_path: Location where to write the certificate to.
    :param key_path: Location where to save the private key.
    """

    # This code is heavily inspired from:
    # https://skippylovesmalorie.wordpress.com/2010/02/12/how-to-generate-a-self-signed-certificate-using-pyopenssl/

    # Clean the certificate destination
    _clean_folder_for_file(cert_path)
    _clean_folder_for_file(key_path)

    # create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "California"
    cert.get_subject().L = "San Rafael"
    cert.get_subject().O = "Autodesk"
    cert.get_subject().OU = "Shotgun Software"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    # 10 years should be enough for everyone
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    # Write the certificate and key back to disk.
    _write_file(cert_path, crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    _write_file(key_path, crypto.dump_privatekey(crypto.FILETYPE_PEM, k))


def is_certificate_registered():
    if sys.platform.startswith("linux"):
        # Adds the certificate for Chrome. For Firefox we'll need to be a bit more inventive.
        cmd = "certutil -L -d sql:$HOME/.pki/nssdb/ | grep Shotgun"
        return_code = subprocess.call(cmd, shell=True)
        # Grep returns 0 when the pattern is matched, 1 when it isn't.
        return return_code == 0
    elif sys.platform == "darwin":
        cmd = "security find-certificate -e localhost | grep \"Shotgun Software\""
        return_code = subprocess.call(cmd, shell=True)
        return return_code == 0
    elif sys.platform == "win32":
        try:
            return "Shotgun Software" in subprocess.check_output("certutil -user -verifystore root localhost", shell=True   )
        except subprocess.CalledProcessError:
            return False


def unregister_certificate():
    pass


def register_certificate(cert_path):
    if sys.platform == "darwin":
        # The SecurityAgent from Apple which prompts for the password to allow an update to the trust settings
        # can sometime freeze. Read more at: https://discussions.apple.com/thread/6300609
        return_code = subprocess.call(
            "security add-trusted-cert -k ~/Library/Keychains/login.keychain -r trustRoot  \"%s\"" % cert_path,
            shell=True
        )
    elif sys.platform == "win32":
        args = ("certutil", "-user", "-addstore", "root", cert_path.replace("/", "\\"))
        return_code = subprocess.call(args, shell=True)
    elif sys.platform.startswith("linux"):
        args = "certutil -A -d sql:$HOME/.pki/nssdb/ -i \"%s\" -n \"Shotgun Desktop Integration\" -t \"TC,C,c\"" % cert_path
        return_code = subprocess.call(args, shell=True)
    return return_code


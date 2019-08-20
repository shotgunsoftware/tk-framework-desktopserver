#!/usr/bin/env python
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
This script will install all dependencies for the browser integration.
A subset of those dependencies, which have binary files, will be
copied to the bin/<os> folder, which dependencies that are only source based
will be stored in source.

Usage:
1. First update requirements.txt top-level dependencies
   required by the browser integration.
2. Run this script on the first OS
3. Run this script on the other OSes with the --bin-only flag so
   you don't update the source folder a second and third time.
"""

import subprocess
import shutil
import sys
import os
import glob
import datetime

copyright = """
# Copyright (c) {} Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
""".format(datetime.datetime.now().year)


# Find which python executable we need to run pip as well as where to store
# binary dependencies.
if sys.platform == "darwin":
    python_bin = "/Applications/Shotgun.app/Contents/Resources/Python/bin/python"
    binary_dst = "bin/mac"
elif sys.platform == "win32":
    python_bin = "C:\\Program Files\\Shotgun\\Python\\python.exe"
    binary_dst = "bin\\win"
else:
    python_bin = "/opt/Shotgun/Python/bin/python"
    binary_dst = "bin/linux"


class UpdateException(Exception):
    pass


def clean_pip():
    freeze_list = pip("freeze").strip().split("\n")
    # No matter why we are leaving this method, we should be removing what was installed.
    for dep in freeze_list:
        pip("uninstall -y {}".format(dep))


def pip(cmd):
    """
    Runs the pip command using the Shotgun Desktop's Python interpreter.
    """
    global env
    return subprocess.check_output(
        "python -m pip".split() + cmd.split()
    )


def git(cmd):
    """
    Runs a git command.
    """
    subprocess.check_output(["git"] + cmd.split())


def main(install_binaries_only):
    """
    Installs all the desktop server dependencies for the current platform.
    """
    dependencies = get_dependencies_to_install()
    update_requirements_file(dependencies)


def get_dependencies_to_install():
    """
    Retrieves the complete list of dependencies and their dependencies.
    """

    if pip("freeze").strip() != "":
        raise UpdateException(
            "Please clean up your Python installation from any dependencies by uninstalling"
            "all of them or pip freeze will contain too many dependencies.\n"
            "For example: \"pip freeze | xargs -n1 pip uninstall -y\""
        )

    try:
        # Pip install all the requirements into the build subfolder.
        pip("install -r requirements.txt")

        # List everything that was installed.
        freeze_list = pip("freeze").strip().split("\n")
    finally:
        clean_pip()
    # autobahn needs to be installed AFTER Twisted, so sorts in alphanumerical order.
    # uppercase T is before lowercase A, so that's good enough.
    return sorted(freeze_list)


def update_requirements_file(dependencies):
    """
    Installs all the dependencies.
    """
    # This is the list of modules we know contain PYDs, SOs and DLLs.
    binary_distributions = ["cffi", "zope.interface", "cryptography"]

    with open("source_only_requirements.txt", "wt") as source:
        source.writelines(copyright)
        with open("binary_requirements.txt", "wt") as binary:
            binary.writelines(copyright)
            for package_locator in dependencies:
                package_name = package_locator.split("==")[0]
                # Figure where the dependency needs to be installed
                if package_name in binary_distributions:
                    binary.writelines([package_locator + "\n"])
                else:
                    source.writelines([package_locator + "\n"])


if __name__ == "__main__":
    # Check if the user wants to only copy binary packages.
    bin_only = "--bin-only" in sys.argv
    if "--clean-pip" in sys.argv:
        clean_pip()
    try:
        main(bin_only)
    except UpdateException as e:
        print(e)

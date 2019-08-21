#!/usr/bin/env python
# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This script will update the list of requirements to install in the bin and source
folders.
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
""".format(
    datetime.datetime.now().year
)


class UpdateException(Exception):
    pass


def pip_freeze():
    """
    Lists all packages installed.
    """
    output = pip("freeze").strip()
    if output == "":
        return []
    else:
        return output.split("\n")


def clean_pip():
    """
    Uninstalls all package with pip
    """
    # No matter why we are leaving this method, we should be removing what was installed.
    for dep in pip_freeze():
        pip("uninstall -y {}".format(dep))


def pip(cmd):
    """
    Runs the pip command.
    """
    return subprocess.check_output("python -m pip".split() + cmd.split())


def git(cmd):
    """
    Runs the git command.
    """
    subprocess.check_output(["git"] + cmd.split())


def main():
    """
    Updates the source_only_requirements.txt and binary_requirements.txt
    files.
    """
    dependencies = get_dependencies_to_install()
    update_requirements_file(dependencies)


def get_dependencies_to_install():
    """
    Retrieves the complete list of dependencies and their dependencies.
    """
    if pip_freeze():
        raise UpdateException(
            "Please clean up your Python installation from any dependencies by uninstalling"
            "all of them or pip freeze will contain too many dependencies.\n"
            "You can clean pip using `update_requirements.py --clean-pip`"
        )

    try:
        # Pip install all the requirements into the build subfolder.
        pip("install -r requirements.txt")

        # List everything that was installed.
        freeze_list = pip_freeze()
    finally:
        clean_pip()
    # autobahn needs to be installed AFTER Twisted, so sorts in alphanumerical order.
    # uppercase T is before lowercase A, so that's good enough.
    return sorted(freeze_list)


def update_requirements_file(dependencies):
    """
    Update the requirement files.
    """
    # This is the list of modules we know contain PYDs, SOs and DLLs.
    binary_distributions = ["cffi", "zope.interface", "cryptography"]

    with open("source/explicit_requirements.txt", "wt") as source:
        source.writelines(copyright)
        with open("bin/explicit_requirements.txt", "wt") as binary:
            binary.writelines(copyright)
            for package_locator in dependencies:
                package_name = package_locator.split("==")[0]
                # Figure which type of dependency it is and write
                # it to the right requirements file.
                if package_name in binary_distributions:
                    binary.writelines([package_locator + "\n"])
                else:
                    source.writelines([package_locator + "\n"])


if __name__ == "__main__":
    if "--clean-pip" in sys.argv:
        clean_pip()
    try:
        main()
    except UpdateException as e:
        print(e)

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
This script will update the list of requirements to install in the bin and
source folders.
"""

import datetime
import os
import subprocess
import sys


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


class UpdateException(Exception):
    pass


class Updater(object):
    def __init__(self):
        # python version
        self._python_version_info = sys.version_info

        self._python_version_dot_format = "{}.{}".format(
            self._python_version_info.major, self._python_version_info.minor)
        self._python_version_underscore_format = "{}_{}".format(
            self._python_version_info.major, self._python_version_info.minor)

        self._is_python_3 = self._python_version_info.major == 3
        self._is_python_2 = self._python_version_info.major == 2
        self._is_python_37 = self._is_python_3 and self._python_version_info.minor == 7
        self._is_python_39 = self._is_python_3 and self._python_version_info.minor == 9

        # packages containing binaries like pyd, so, dll
        self._binary_distributions = [
            "cffi",
            "zope.interface",
            "cryptography",
        ]

        # framework base dir (python, resources, root)
        self._base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.realpath(__file__))))

        # python resources dir
        self._python_resources_dir = os.path.join(
            self._base_dir,
            "resources",
            "python",
        )

        # dir of packages distributed as source
        self._sources_dir = os.path.join(
            self._python_resources_dir,
            "src",
        )

        # dir of packages distributed as binary
        self._bin_dir = os.path.join(
            self._python_resources_dir,
            "bin",
        )

        # paths for final requirements files
        self._source_reqs_2_7_dir = os.path.join(
            self._sources_dir,
            "2.7",
        )
        self._source_reqs_2_7_path = os.path.join(
            self._source_reqs_2_7_dir,
            "explicit_requirements.txt"
        )

        self._source_reqs_3_7_dir = os.path.join(
            self._sources_dir,
            "3.7",
        )
        self._source_reqs_3_7_path = os.path.join(
            self._source_reqs_3_7_dir,
            "explicit_requirements.txt"
        )

        self._source_reqs_3_9_dir = os.path.join(
            self._sources_dir,
            "3.9",
        )
        self._source_reqs_3_9_path = os.path.join(
            self._source_reqs_3_9_dir,
            "explicit_requirements.txt"
        )

        self._bin_reqs_2_7_dir = os.path.join(
            self._bin_dir,
            "2.7",
        )
        self._bin_reqs_2_7_path = os.path.join(
            self._bin_reqs_2_7_dir,
            "explicit_requirements.txt"
        )

        self._bin_reqs_3_7_dir = os.path.join(
            self._bin_dir,
            "3.7",
        )
        self._bin_reqs_3_7_path = os.path.join(
            self._bin_reqs_3_7_dir,
            "explicit_requirements.txt"
        )

        self._bin_reqs_3_9_dir = os.path.join(
            self._bin_dir,
            "3.9",
        )
        self._bin_reqs_3_9_path = os.path.join(
            self._bin_reqs_3_9_dir,
            "explicit_requirements.txt"
        )

    def _pip_freeze(self):
        """List all packages installed."""
        output = self._pip("freeze").strip()
        if output == "":
            return []
        else:
            return output.split("\n")

    def _clean_pip(self):
        """Uninstall all packages with pip."""
        # No matter why we are leaving this method, we should be removing
        # what was installed.
        for dependency in self._pip_freeze():
            cmd = "uninstall -y {}".format(dependency)
            self._pip(cmd)

    def _pip(self, cmd):
        """Run the pip command."""
        pip_cmd = "python -m pip".split() + cmd.split()
        output = subprocess.check_output(pip_cmd)

        if self._is_python_3:
            output = output.decode("utf-8")

        return output

    @staticmethod
    def _git(cmd):
        """Run the git command."""
        git_cmd = ["git"] + cmd.split()
        subprocess.check_output(git_cmd)

    def _get_dependencies_to_install(self):
        """Retrieve the full list of dependencies after a pip install."""
        if self._pip_freeze():
            raise UpdateException(
                "Please clean up your Python installation from any "
                "dependencies by uninstalling all of them or pip freeze "
                "will contain too many dependencies.\nYou can clean pip "
                "using `update_requirements.py --clean-pip`"
            )

        try:
            # pip install all the requirements into the build subfolder.
            self._pip("install -r requirements/{}/requirements.txt".format(
                self._python_version_dot_format
            ))

            # list everything that was installed.
            freeze_list = self._pip_freeze()
        finally:
            self._clean_pip()

        # autobahn needs to be installed AFTER Twisted, so sorts in
        # alphanumerical order. Uppercase T is before lowercase A, so that's
        # good enough.
        return sorted(freeze_list)

    def _update_requirements_file(self, dependencies):
        """
        Update the requirement files.
        """
        version = self._python_version_underscore_format
        source_dir = getattr(self, "_source_reqs_{}_dir".format(version))
        source_reqs_path = getattr(self, "_source_reqs_{}_path".format(
            version))
        bin_dir = getattr(self, "_bin_reqs_{}_dir".format(version))
        bin_reqs_path = getattr(self, "_bin_reqs_{}_path".format(version))

        for path in [source_dir, bin_dir]:
            if not os.path.isdir(path):
                os.makedirs(path)

        with open(source_reqs_path, 'w') as source_handler, \
                open(bin_reqs_path, 'wt') as bin_handler:
            source_handler.writelines(copyright)
            bin_handler.writelines(copyright)

            for dependency in dependencies:
                package_name = dependency.split("==")[0]

                # Figure which type of dependency it is and write
                # it to the right requirements file.
                requirement_to_add = [dependency + "\n"]
                if package_name in self._binary_distributions:
                    bin_handler.writelines(requirement_to_add)
                else:
                    source_handler.writelines(requirement_to_add)

    @staticmethod
    def _clean_before_update():
        return "--clean-pip" in sys.argv

    def go(self):
        """Update the source and binary requirements files."""
        if self._clean_before_update():
            self._clean_pip()

        dependencies = self._get_dependencies_to_install()
        self._update_requirements_file(dependencies)


def main():
    updater = Updater()
    updater.go()


if __name__ == "__main__":
    main()

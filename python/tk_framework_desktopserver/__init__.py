# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys

import sgtk.util

# framework path
base_path = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

python_path = os.path.join(base_path, "resources", "python")
binaries_path = os.path.join(python_path, "bin")

_py_version = sys.version_info
_version_dir = "{}.{}".format(_py_version.major, _py_version.minor)

if sgtk.util.is_macos():
    sys.path.insert(0, os.path.join(binaries_path, _version_dir, "mac"))
elif sgtk.util.is_windows():
    sys.path.insert(0, os.path.join(binaries_path, _version_dir, "win"))
elif sgtk.util.is_linux():
    sys.path.insert(0, os.path.join(binaries_path, _version_dir, "linux"))

sys.path.insert(0, os.path.join(python_path, "src", _version_dir))

from .server import Server
from .server import ServerProtocol
from .settings import Settings
from .process_manager import ProcessManager
from .certificates import get_certificate_handler
from .logger import get_logger
from .shotgun import get_shotgun_api
from .errors import (
    MissingCertificateError,
    PortBusyError,
    MissingConfigurationFileError,
    BrowserIntegrationError,
)

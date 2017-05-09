# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk


def get_logger(child_logger):
    """
    Returns the logger used by this framework.
    """
    try:
        return sgtk.platform.get_logger(child_logger)
    except Exception:
        return sgtk.LogManager.get_logger("tk-framework.desktopserver.%s" % child_logger)

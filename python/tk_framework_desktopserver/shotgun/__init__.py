# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

def get_shotgun_api(protocol_version, host, process_manager, semaphore):
    """

    """
    if protocol_version == 1:
        from .api_v1 import ShotgunAPI
    elif protocol_version == 2:
        from .api_v2 import ShotgunAPI
    else:
        raise RuntimeError("Unsupported protocol version: %s" % protocol_version)

    return ShotgunAPI(host, process_manager, semaphore)

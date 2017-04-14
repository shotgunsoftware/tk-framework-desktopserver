# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# We want class-level variables to persist, so we'll setup a cache here
# that the factory functuon below populates.
from . import api_v1
from . import api_v2

def get_shotgun_api(protocol_version, host, process_manager, wss_key):
    """
    A factory function that returns an rpc API instance. The given
    protocol version will be taken into account when determining which
    API version to instantiate and return.

    :param int protocol_version: The protocol version that the returned
        API instance must support.
    :param host: The message host.
    :param process_manager: A process manager. This is only used by the
        protocol verion 1 API, but provided to all APIs for the sake of
        consistency.
    :param str wss_key: The unique key associated with a WSS connection.
        This key is provided by the autobahn libary's ConnectionRequest
        object at the time a new WSS connection is made.

    :returns: An RPC API instance appropriate for the given protocol
        version.
    """
    if protocol_version == 1:
        return api_v1.ShotgunAPI(host, process_manager, wss_key)
    elif protocol_version == 2:
        return api_v2.ShotgunAPI(host, process_manager, wss_key)
    else:
        raise RuntimeError("Unsupported protocol version: %s" % protocol_version)

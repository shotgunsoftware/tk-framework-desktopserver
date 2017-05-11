# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Constants here are in use in api_v2. The legacy api_v1 does not currently
# make use of them.
import os

# RPC return codes.
SUCCESSFUL_LOOKUP = 0
UNSUPPORTED_ENTITY_TYPE = 2
CACHING_ERROR = 3
COMMAND_SUCCEEDED = 0
COMMAND_FAILED = 1

# Pipeline configurations.
OVERRIDE_CONFIG_PATH = os.environ.get("TK_BOOTSTRAP_CONFIG_OVERRIDE")

if OVERRIDE_CONFIG_PATH is not None:
    BASE_CONFIG_URI = "sgtk:descriptor:dev?path=%s" % OVERRIDE_CONFIG_PATH
else:
    BASE_CONFIG_URI = "sgtk:descriptor:app_store?name=tk-config-basic"

ENGINE_NAME = "tk-shotgun"
PUBLISHED_FILE_ENTITY = "PublishedFile"

# The base set of supported entity types. All others are provided
# by the PublishedFile entity's schema, where we pull the list of
# entity types that it can be linked to. Out of the box, this will
# include things like Asset, Shot, Episode, and Level.
#
# Once combined with the PublishedFile's entity link types, this
# forms the list of entity types that we provide action menu items
# for. Any entity type requesting action menu items that is not in
# the whitelist is informed that none will be provided.
BASE_ENTITY_TYPE_WHITELIST = set([
    "Project",
    PUBLISHED_FILE_ENTITY,
    "Sequence",
    "Task",
    "Version",
])

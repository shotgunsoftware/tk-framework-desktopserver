# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


class MockConfigDescriptor(object):
    def __init__(self, path, is_immutable):
        self._is_immutable = is_immutable
        self._path = path
        self._uri = "sgtk:descriptor:dev?path=%s" % self._path

    def get_path(self):
        return self._path

    def is_immutable(self):
        return self._is_immutable

    def get_uri(self):
        return self._uri



# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os, sys
# import unittest2 as unittest
from twisted.trial import unittest

python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path = [python_path] + sys.path

from tk_server import Server
import logging

class TestLocalization(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestLocalization,self).__init__(*args, **kwargs)

    def setUp(self):
        #open_script = os.path.join(os.path.dirname(__file__), 'open_script.py')
        #os.environ["SHOTGUN_PLUGIN_LAUNCHER"] = 'python "' + open_script + '"'
        pass

    def test_echo(self):
        pass

    def test_open(self):
        # Test file open
        pass

    def test_localization(self):
        pass

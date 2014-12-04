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
from twisted.trial import unittest
from twisted.internet import defer

python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "../..", "python"))
sys.path = [python_path] + sys.path

from tk_server import Server
from client import Client, TestEchoClientProtocol

class TestLocalization(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestLocalization,self).__init__(*args, **kwargs)
        self.client = None
        self.server = None

    def setUp(self):
        #open_script = os.path.join(os.path.dirname(__file__), 'open_script.py')
        #os.environ["SHOTGUN_PLUGIN_LAUNCHER"] = 'python "' + open_script + '"'
        pass

    def tearDown(self):
        if self.client and self.server:
            self.server.listener.stopListening()
            self.client.connection.disconnect()

    def _echo_result(self, answer):
        self.assertEqual(answer["message"], self._echo_message)

    def test_echo(self):
        deferred = defer.Deferred()
        self._echo_message = 'Testing echo!'

        self.server = Server()
        self.server.start(True, os.path.join(os.path.dirname(__file__), "../../resources/keys"))

        self.client = Client()
        protocol = TestEchoClientProtocol
        protocol._deferred = deferred
        protocol._myMessage = self._echo_message
        self.client.start(protocol)

        deferred.addCallback(self._echo_result)
        kjnasdfmnafdmn
        return deferred

    def test_open(self):
        # Test file open
        pass

    def test_localization(self):
        pass

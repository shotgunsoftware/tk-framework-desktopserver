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

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from twisted.trial import unittest
from twisted.internet import defer


from tk_server import Server
from common import Client
from common import TestEchoClientProtocol

class TestLocalization(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestLocalization,self).__init__(*args, **kwargs)
        self.client = None
        self.server = None

    def setUp(self):
        self._deferred = None
        self._echo_message = None

    def tearDown(self):
        if self.client and self.server:
            # It is necessary to close server and all connections in order for the
            # reactor tied to the test to be freed.
            self.server.listener.stopListening()
            self.client.connection.disconnect()

    def _echo_result(self, answer):
        self.assertEqual(answer["message"], self._echo_message)

    def _setup_protocol(self, protocol):
        self._echo_message = 'Testing echo!'

        protocol._myMessage = self._echo_message
        protocol._deferred = self._deferred

    def test_echo(self):
        self._deferred = defer.Deferred()

        self.server = Server()
        self.server.start(True, os.path.join(os.path.dirname(__file__), "../../resources/keys"))

        self.client = Client(self._setup_protocol)
        protocol = TestEchoClientProtocol
        self.client.start(protocol)

        self._deferred.addCallback(self._echo_result)

        return self._deferred

# -*- coding: utf-8 -*-

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

class TestEcho(unittest.TestCase):
    """
    Testing server echo API
    """

    def __init__(self, *args, **kwargs):
        """
        TestCase Constructor
        """
        super(TestEcho,self).__init__(*args, **kwargs)
        self.client = None
        self.server = None
        self.keys_path = os.path.join(os.path.dirname(__file__), "../../resources/keys")

    def setUp(self):
        """
        Setup TestCase
        """

        self._deferred = defer.Deferred()

        self.server = Server()
        self.server.start(True, self.keys_path)

    def tearDown(self):
        """
        Test tearDown method when TestCase is completed.
        """

        # It is necessary to close server and all connections in order for the
        # reactor tied to the test to be freed.
        self.__disconnect()

        self._deferred = None
        self._echo_message = None

    def __disconnect(self):
        """
        Disconnect client/server
        """
        if self.client:
            self.client.connection.disconnect()
        if self.server:
            self.server.listener.stopListening()

    def _start_client(self):
        """
        Start a client to communication with server
        """
        self.client = Client(self._setup_protocol)
        self.client.start(TestEchoClientProtocol)

    def _echo_result(self, answer):
        """
        Result testing of echo protocol
        """
        self.assertEqual(answer["message"], self._echo_message)

    def _setup_protocol(self, protocol):
        """
        Since there are no protocol factory init methods, this allows a way to setup protocol members
        right after creation.
        """
        protocol._myMessage = self._echo_message
        protocol._deferred = self._deferred

    def test_echo(self):
        """
        Simple echo test.
        Sends a message to server and expect to receive same message on a client.
        """
        self._echo_message = 'Testing echo!'
        self._start_client()
        self._deferred.addCallback(self._echo_result)

        return self._deferred

    def test_echo_utf8(self):
        """
        Echo test using Utf8 characters.
        Since server encodes/decodes all socket messages, tests the basic functionality of messages to
        support international characters.
\       """
        self._echo_message = u'Testing echo! -- 你的舞跳得这么好漂亮的女士 --'
        self._start_client()
        self._deferred.addCallback(self._echo_result)

        return self._deferred

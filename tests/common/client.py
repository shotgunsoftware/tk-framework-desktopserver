# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

from twisted.python import log
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketClientFactory, connectWS

from echo_protocol import EchoClientProtocol
from testecho_protocol import TestEchoClientProtocol

class Client(object):
    """
    Client Fixture
    """

    def __init__(self, onProtocolCreated=None):
        self.onProtocolCreated = onProtocolCreated

    def _buildProtocol(self, *args, **kwargs):
        protocol = WebSocketClientFactory.buildProtocol(self.factory, *args, **kwargs)

        if self.onProtocolCreated:
            self.onProtocolCreated(protocol)

        return protocol

    def start(self, protocol=EchoClientProtocol, url="wss://localhost:9000"):
        log.startLogging(sys.stdout)

        ## create a WS server factory with our protocol
        ##
        factory = WebSocketClientFactory(url, debug = False)
        factory.buildProtocol = self._buildProtocol
        factory.protocol = protocol

        self.factory = factory

        ## SSL client context: default
        ##
        if factory.isSecure:
            contextFactory = ssl.ClientContextFactory()
        else:
            contextFactory = None

        self.connection = connectWS(factory, contextFactory)


def setProtocolOptions(protocol):
    protocol._myMessage = "aahahah"
    protocol._deferred = defer.Deferred()

if __name__ == '__main__':
    """
    Run Python Client
    """
    from twisted.internet import defer

    a = Client()
    a.start()

    reactor.run()

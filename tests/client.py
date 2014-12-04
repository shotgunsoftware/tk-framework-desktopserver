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
import json

from twisted.python import log
from twisted.internet import reactor, ssl

from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, \
    connectWS



class EchoClientProtocol(WebSocketClientProtocol):
    """
    Simple Test Client protocol that continuously sends/receives messages on connection opened
    """
    def sendHello(self):
        cmd = {}
        cmd["name"] = "echo"
        cmd["data"] = {}
        cmd["data"]["message"] = "Hello, world!"

        payload = json.dumps(cmd, ensure_ascii = False).encode("utf8")
        self.sendMessage(payload)

    def onOpen(self):
        self.sendHello()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            print("Text message received: {}".format(payload.decode('utf8')))
        reactor.callLater(1, self.sendHello)


class TestEchoClientProtocol(WebSocketClientProtocol):
    """
    Simple Test Client protocol that sends/receives messages on connection opened
    """

    _myMessage = None
    _deferred = None

    def sendHello(self):
        cmd = {}
        cmd["name"] = "echo"
        cmd["data"] = {}
        cmd["data"]["message"] = TestEchoClientProtocol._myMessage

        payload = json.dumps(cmd, ensure_ascii = False).encode("utf8")
        self.sendMessage(payload)

    def onOpen(self):
        self.sendHello()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            answer = json.loads(payload.decode("utf8"))
            TestEchoClientProtocol._deferred.callback(answer)
        else:
            TestEchoClientProtocol._deferred.callback(payload)


class Client(object):
    """
    Client Fixture
    """

    def start(self, protocol=EchoClientProtocol, url="wss://localhost:9000"):
        log.startLogging(sys.stdout)

        ## create a WS server factory with our protocol
        ##
        factory = WebSocketClientFactory(url, debug = False)
        factory.protocol = protocol

        ## SSL client context: default
        ##
        if factory.isSecure:
            contextFactory = ssl.ClientContextFactory()
        else:
            contextFactory = None

        self.connection = connectWS(factory, contextFactory)

if __name__ == '__main__':
    """
    Run Python Client
    """
    from twisted.internet import defer

    a = Client()
    #a.start(TestEchoClientProtocol(defer.Deferred(), 'ahaha'))
    protocol = TestEchoClientProtocol
    protocol._deferred = defer.Deferred()
    protocol._myMessage = "ahahahah"
    a.start(protocol)
    #a.start()

    reactor.run()

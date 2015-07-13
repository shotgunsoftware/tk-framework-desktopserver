# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
from autobahn.twisted.websocket import WebSocketClientProtocol

from tk_server.server_protocol import ServerProtocol
import time


class TestEchoClientProtocol(WebSocketClientProtocol):
    """
    Simple Test Client protocol that sends/receives messages on connection opened
    """

    def __init__(self):
        self._myMessage = None
        self._deferred = None

    def sendHello(self):
        cmd = {}
        cmd["id"] = int(time.mktime(time.localtime()))
        cmd["protocol_version"] = ServerProtocol.PROTOCOL_VERSION
        cmd["command"] = {}
        cmd["command"]["name"] = "echo"
        cmd["command"]["data"] = {}
        cmd["command"]["data"]["message"] = self._myMessage

        payload = json.dumps(cmd, ensure_ascii=False).encode("utf8")
        self.sendMessage(payload)

    def onOpen(self):
        self.sendHello()

    def onMessage(self, payload, is_binary):
        if not is_binary:
            answer = json.loads(payload.decode("utf8"))
            self._deferred.callback(answer)
        else:
            self._deferred.callback(payload)

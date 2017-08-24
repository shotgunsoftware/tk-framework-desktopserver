# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import os
import sys
import base64
import json


from mock import patch, Mock

from tank_test.tank_test_base import setUpModule # noqa

import sgtk
from tank_vendor.shotgun_api3.lib.mockgun import Shotgun

sys.path.insert(0, "/Users/jfboismenu/gitlocal/tk-framework-desktopserver/resources/python/dist/mac")
sys.path.insert(0, "/Users/jfboismenu/gitlocal/tk-framework-desktopserver/python")

# Lazy init since the framework adds the twisted libs.
from twisted.trial import unittest
from twisted.internet import ssl
from autobahn.twisted.websocket import connectWS, WebSocketClientFactory, WebSocketClientProtocol
from twisted.internet.defer import Deferred
from twisted.internet import reactor
from cryptography.fernet import Fernet

from twisted.internet import base
base.DelayedCall.debug = True


class TestServer(unittest.TestCase):
    """
    Tests for various caching-related methods for api_v2.
    """

    def setUp(self):
        super(TestServer, self).setUp()

        # Compute the path to the unit test fixtures.
        fixtures_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))

        # Make sure Qt is initialized
        from PySide import QtCore, QtGui
        # Init Qt
        if not QtGui.QApplication.instance():
            QtGui.QApplication([])

        # We're not initializing Toolkit, but some parts of the code are going to expect Toolkit to be
        # initialized, so initialize that is needed.
        sgtk.platform.qt.QtCore = QtCore
        sgtk.platform.qt.QtGui = QtGui

        # Create a mockgun instance and add support for the _call_rpc method which is used to get
        # the secret.
        host = "https://127.0.0.1"
        Shotgun.set_schema_paths(
            os.path.join("/Users/jfboismenu/gitlocal/tk-core/tests/fixtures", "mockgun", "schema.pickle"),
            os.path.join("/Users/jfboismenu/gitlocal/tk-core/tests/fixtures", "mockgun", "schema_entity.pickle")
        )
        self._mockgun = Shotgun(host)
        self._mockgun.server_info = {
            "shotgunlocalhost_browser_integration_enabled": True
        }
        self._mockgun._call_rpc = self._call_rpc
        self._ws_server_secret = base64.urlsafe_b64encode(os.urandom(32))

        # Create the user who will be making all the requests.
        self._user = self._mockgun.create("HumanUser", {"name": "Gilles Pomerleau"})

        # Pretend there is a current bundle loaded.
        patched = patch("sgtk.platform.current_bundle", return_value=Mock(shotgun=self._mockgun))
        patched.start()
        self.addCleanup(patched.stop)

        # Initialize the websocket server.
        from tk_framework_desktopserver import Server, shotgun
        self.server = Server(
            keys_path=os.path.join(fixtures_root, "certificates"),
            encrypt=True,
            host=host,
            user_id=self._user["id"],
            port=9000
        )

        patched = patch.object(
            shotgun, "get_shotgun_api",
            return_value=Mock(PUBLIC_API_METHODS=["repeat_value"], repeat_value=lambda data: data["value"] * 2)
        )
        patched.start()
        self.addCleanup(patched.stop)

        # Do not call server.start() as this will also launch the reactor, which was already
        # launched by twisted.trial
        self.server._start_server()

        # Create the client connection to the websocket server.
        context_factory = ssl.DefaultOpenSSLContextFactory(
            os.path.join(fixtures_root, "certificates", "server.key"),
            os.path.join(fixtures_root, "certificates", "server.crt")
        )

        # This will be returned by the setUp method to signify that we're done setuping the test.
        connection_ready_deferred = Deferred()
        test_case = self

        class ClientProtocol(WebSocketClientProtocol):
            """
            This class will use Deferred instances to notify that the test is ready to start
            and to notify the test that a payload has arrived.
            """
            def __init__(self):
                super(ClientProtocol, self).__init__()
                self._on_message_deferred = None

            def onConnect(self, response):
                """
                Informs the unit test framework that we're connected to the server.
                """
                test_case.client_protocol = self
                connection_ready_deferred.callback(None)

            def sendMessage(self, payload):
                """
                Sends a message to the websocket server.

                :returns: A deferred that will be called when the associated response comes back.

                .. note::
                    Only one message can be sent at a time at the moment.
                """
                super(ClientProtocol, self).sendMessage(payload, isBinary=False)
                self._on_message_deferred = Deferred()
                return self._on_message_deferred

            def onMessage(self, payload, is_binary):
                """
                Invokes any callback attached to the last Deferred returned by sendMessage.
                """
                d = self._on_message_deferred
                self._on_message_deferred = None
                d.callback(payload)

            # def connectionLost(self, reason):
            #     if self._on_message_deferred:
            #         self._on_message_deferred.errback(reason)

        # Create the websocket connection to the server.
        client_factory = WebSocketClientFactory("wss://localhost:9000")
        client_factory.origin = "https://127.0.0.1"
        client_factory.protocol = ClientProtocol
        self.client = connectWS(client_factory, context_factory, timeout=2)

        # When the test ends, we need to stop listening.
        self.addCleanup(lambda: self.server.listener.stopListening())
        self.addCleanup(lambda: self.client.disconnect())

        # Return the deferred that will be called then the setup is completed.
        return connection_ready_deferred

    def _call_rpc(self, name, paylad, *args):
        if name == "retrieve_ws_server_secret":
            return {
                "ws_server_secret": self._ws_server_secret
            }
        else:
            raise NotImplementedError("The RPC %s is not implemented." % name)

    def _chain_calls(self, *calls):
        """
        This will chain calls to the websocket server. Each method must follow this pattern:

            def method(result):
                d = Deferred()
                ...
                return d

        The last method must not return.

        If the test doesn't complete under 5 seconds, it will be aborted.

        :returns: The Deferred that will be invoked when the test succeeds or fails.
        """
        done = Deferred()
        done.addTimeout(5, reactor)
        self._call_next(None, list(calls), done)
        return done

    def _call_next(self, payload, calls, done):
        """
        Calls the next method in the calls array. Calls ``done`` when there is an error
        or all the calls have been executed.
        """
        try:
            # Invoke the next method in the chain.
            d = calls[0](payload)
            calls.pop(0)
            # If we got a defered back
            if d and len(calls) == 0:
                # Make sure there are more calls to make
                done.errback(RuntimeError("Got a deferred but call chain is empty."))
            elif not d and len(calls) != 0:
                done.errback(RuntimeError("Call chain is not empty but no deferred was returned."))

            # If a deferred is returned, we must invoke the remaining calls.
            if d:
                d.addCallback(lambda payload: self._call_next(payload, calls, done))
            else:
                done.callback(None)
        except Exception as e:
            # There was an error, abort the test right now!
            done.errback(e)

    def _send_payload(self, payload, encrypt):
        """
        Sends a payload as is to the server.
        """
        if encrypt:
            payload = self._fernet.encrypt(payload)
        return self.client_protocol.sendMessage(payload)

    def _send_message(self, command, data, encrypt):
        """
        Sends
        """
        payload = {
            "id": 1,
            "protocol_version": 2,

            "command": {
                "name": command,
                "data": {
                    "user": {
                        "entity": {
                            "id": self._user["id"]
                        }
                    }
                }
            }
        }
        if data:
            payload["command"]["data"].update(data)
        return self._send_payload(
            json.dumps(payload),
            encrypt=encrypt
        )

    # def test_connecting(self):
    #     """
    #     Makes sure our unit tests framework can connect
    #     """
    #     self.assertEqual(self.client.state, "connected")

    def test_calls_encrypted(self):
        """
        Ensures that calls are encrypted after get_ws_server_is is invoked.
        """
        def step1(_):
            return self._send_message("get_ws_server_id", None, encrypt=False)

        def step2(payload):
            self._fernet = Fernet(self._ws_server_secret)
            return self._send_message("repeat_value", {"value": "hello"}, encrypt=True)

        def step3(payload):
            payload = self._fernet.decrypt(payload)

        return self._chain_calls(step1, step2, step3)

    # def test_rpc_before_encrypt(self):

    #     def step1(payload):
    #         return self._send_payload("get_protocol_version", encrypt=False)

    #     def step2(payload):
    #         payload = json.loads(payload)
    #         self.assertEqual(payload["protocol_version"], 2)
    #         d = self._send_message("get_ws_server_id", None, encrypt=False)
    #         return d

    #     def step3(payload):
    #         payload = json.loads(payload)
    #         self.assertIn("ws_server_id", payload["reply"])
    #         self.assertIsNotNone(payload["reply"]["ws_server_id"])

    #     return self._chain_calls(step1, step2, step3)

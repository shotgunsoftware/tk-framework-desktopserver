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

from twisted.internet import base
base.DelayedCall.debug = True


class MockUser(object):

    def __init__(self, host, login):
        Shotgun.set_schema_paths(
            "/Users/jfboismenu/gitlocal/tk-core/tests/fixtures/mockgun/schema.pickle",
            "/Users/jfboismenu/gitlocal/tk-core/tests/fixtures/mockgun/schema_entity.pickle"
        )
        self._shotgun = Shotgun(host)
        self._shotgun.server_info = {
            "shotgunlocalhost_browser_integration_enabled": True
        }
        self._shotgun._call_rpc = self._call_rpc

        self.host = host
        self.login = login

    def create_sg_connection(self):
        return self._shotgun

    def _call_rpc(self, name, paylad, *args):
        if name == "retrieve_ws_server_secret":
            return {
                "ws_server_secret": base64.urlsafe_b64encode(os.urandom(32))
            }
        else:
            raise NotImplementedError("The RPC %s is not implemented." % name)


class TestServer(unittest.TestCase):
    """
    Tests for various caching-related methods for api_v2.
    """

    def tearDown(self):
        super(TestServer, self).tearDown()

        sgtk.set_authenticated_user(None)

    def setUp(self):
        super(TestServer, self).setUp()

        from PySide import QtCore, QtGui

        # Init Qt
        if not QtGui.QApplication.instance():
            QtGui.QApplication([])

        sgtk.platform.qt.QtCore = QtCore
        sgtk.platform.qt.QtGui = QtGui

        from tk_framework_desktopserver import Server

        self._auth_user = MockUser("https://127.0.0.1", "test_user")
        sgtk.set_authenticated_user(self._auth_user)
        self._mockgun = self._auth_user.create_sg_connection()

        # Create the user who will be making all the requests.
        self._user = self._mockgun.create("HumanUser", {"name": "Gilles Pomerleau"})

        patched = patch("sgtk.platform.current_bundle", return_value=Mock(shotgun=self._mockgun))
        patched.start()
        self.addCleanup(patched.stop)

        # self.framework.launch_desktop_server("https://127.0.0.1", self._user["id"])
        # self.assertTrue(self.framework._integration_enabled)

        self.server = Server(
            "/Users/jfboismenu/gitlocal/tk-framework-desktopserver/tests/fixtures/certificates",
            True,
            "https://127.0.0.1",
            self._user["id"],
            9000
        )

        # Do not call server.start() as this will also launch the reactor, which was already
        # launched by twisted.trial
        self.server._start_server()

        context_factory = ssl.DefaultOpenSSLContextFactory(
            "/Users/jfboismenu/gitlocal/tk-framework-desktopserver/tests/fixtures/certificates/server.key",
            "/Users/jfboismenu/gitlocal/tk-framework-desktopserver/tests/fixtures/certificates/server.crt"
        )

        connection_ready_deferred = Deferred()
        test_case = self

        class ClientProtocol(WebSocketClientProtocol):
            def __init__(self):
                super(ClientProtocol, self).__init__()

            def onConnect(self, response):
                test_case.client_protocol = self
                connection_ready_deferred.callback(None)

            def sendMessage(self, payload):
                super(ClientProtocol, self).sendMessage(payload, isBinary=False)
                self._on_message_defered = Deferred()
                return self._on_message_defered

            def onMessage(self, payload, is_binary):
                self._on_message_defered.callback(payload)

        client_factory = WebSocketClientFactory("wss://localhost:9000")
        client_factory.protocol = ClientProtocol
        client_factory.listener = self.server.listener

        # Create a deferred that will be signaled when the unit test is completed.
        self.client = connectWS(client_factory, context_factory, timeout=2)

        self.addCleanup(lambda: self.server.listener.stopListening())

        return connection_ready_deferred

    # def test_listening(self):
    #     """
    #     Makes sure our unit tests framework can listen to the port.
    #     """
    #     return self.server.listener.stopListening()

    def test_connecting(self):
        """
        Makes sure our unit tests framework can connect to the port.
        """
        # Get the protocol version.
        self.client.disconnect()

    def _chain_calls(self, *calls):
        done = Deferred()
        done.addTimeout(5, reactor)
        self._call_next(None, list(calls), done)
        return done

    def _call_next(self, payload, calls, done):
        try:
            # Invoke the next method in the chain.
            d = calls[0](payload)
            calls.pop(0)
            # If we got a defered back
            if d and len(calls) == 0:
                # Make sure there are more calls to make
                self.client.disconnect()
                done.errback(RuntimeError("Got a deferred but call chain is empty."))
            elif not d and len(calls) != 0:
                self.client.disconnect()
                done.errback(RuntimeError("Call chain is not empty but no deferred was returned."))

            # If a deferred is returned, we must invoke the remaining calls.
            if d:
                d.addCallback(lambda payload: self._call_next(payload, calls, done))
            else:
                self.client.disconnect()
                done.callback(None)
        except Exception as e:
            # There was an error, abort the test right now!
            done.errback(e)

    def _send_payload(self, payload, encrypt):
        return self.client_protocol.sendMessage(payload)

    def _send_message(self, command, data, encrypt):
        return self._send_payload(
            json.dumps(
                {
                    "id": 1,
                    "protocol_version": 2,
                    "command": {
                        "name": command,
                        "data": data
                    }
                }
            ),
            encrypt=encrypt
        )

    def test_calls_encrypted(self):
        """
        Ensures that calls are encrypted after get_ws_server_is is invoked.
        """
        def step1(_):
            return self._send_message("get_ws_server_id", None, encrypt=False)

        def step2(payload):
            payload = json.loads(payload)
            self.assertIn("ws_server_id", payload["reply"])
            self.assertIsNotNone(payload["reply"]["ws_server_id"])

        #def step3(payload)

        return self._chain_calls(step1, step2)

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

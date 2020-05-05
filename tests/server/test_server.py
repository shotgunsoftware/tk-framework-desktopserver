# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from __future__ import print_function
import os
import sys
import base64
import json
import contextlib
import socket
import websocket

from mock import patch, Mock

from tank_test.tank_test_base import setUpModule  # noqa

import sgtk
from tank_vendor.shotgun_api3.lib.mockgun import Shotgun

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
fixtures_root = os.path.join(repo_root, "tests", "fixtures")

sys.path.insert(0, os.path.join(repo_root, "python"))

# Mock Qt since we don't have it.
sgtk.platform.qt.QtCore = Mock()
sgtk.platform.qt.QtGui = Mock()

# Doing this import will add the twisted librairies
import tk_framework_desktopserver  # noqa

from twisted.trial import unittest
from twisted.internet import ssl
from autobahn.twisted.websocket import (
    connectWS,
    WebSocketClientFactory,
    WebSocketClientProtocol,
)
from twisted.internet.defer import Deferred
from twisted.internet import reactor, threads
from cryptography.fernet import Fernet

from twisted.internet import base

base.DelayedCall.debug = True


# Source: https://stackoverflow.com/a/45690594/10429444
def find_free_port():
    """
    Finds a free port on the current computer.
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class MockShotgunApi(object):
    """
    Mocks the v2 protocol with a custom method.
    """

    PUBLIC_API_METHODS = ["repeat_value", "missing_attribute"]

    def __init__(self, host, process_manager, wss_key):
        self._host = host

    def repeat_value(self, payload):
        self._host.reply({"value": payload["value"] * 3})


class TestServerBase(unittest.TestCase):
    def setUpClientServer(
        self,
        use_encryption=False,
        origin="https://site.shotgunstudio.com",
        host_aliases=None,
    ):

        if not host_aliases:
            host_aliases = ["site.shotgunstudio.com"]

        self._use_encryption = use_encryption

        # Create a mockgun instance and add support for the _call_rpc method which is used to get
        # the secret.
        sg_host = "https://127.0.0.1"
        Shotgun.set_schema_paths(
            os.path.join(fixtures_root, "mockgun", "schema.pickle"),
            os.path.join(fixtures_root, "mockgun", "schema_entity.pickle"),
        )
        self._mockgun = Shotgun(sg_host)
        self._mockgun._call_rpc = self._call_rpc
        self._mockgun.server_info = {
            "shotgunlocalhost_browser_integration_enabled": True
        }

        # Set up an encryption key.
        self._ws_server_secret = base64.urlsafe_b64encode(os.urandom(32))

        self._fernet = Fernet(self._ws_server_secret)

        # Create the user who will be making all the requests.
        self._user = self._mockgun.create("HumanUser", {"name": "Gilles Pomerleau"})

        # Pretend there is a current bundle loaded.
        patched = patch(
            "sgtk.platform.current_bundle", return_value=Mock(shotgun=self._mockgun)
        )
        patched.start()
        self.addCleanup(patched.stop)

        from tk_framework_desktopserver import Server, shotgun

        patched = patch.object(Server, "Notifier", new=Mock())
        patched.start()
        self.addCleanup(patched.stop)

        port = find_free_port()

        # Initialize the websocket server.
        self.server = Server(
            keys_path=os.path.join(fixtures_root, "certificates"),
            encrypt=use_encryption,
            host="https://site.shotgunstudio.com",
            user_id=self._user["id"],
            host_aliases=host_aliases,
            port=port,
            uses_intermediate_certificate_chain=True,
        )

        patched = patch.object(
            shotgun,
            "get_shotgun_api",
            new=lambda _, host, process_manager, wss_key: MockShotgunApi(
                host, process_manager, wss_key
            ),
        )
        patched.start()
        self.addCleanup(patched.stop)

        # Do not call server.start() as this will also launch the reactor, which was already
        # launched by twisted.trial
        self.server._start_server()

        # Create the client connection to the websocket server.
        context_factory = ssl.DefaultOpenSSLContextFactory(
            os.path.join(fixtures_root, "certificates", "server.key"),
            os.path.join(fixtures_root, "certificates", "server.crt"),
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

            def sendMessage(self, payload, is_binary):
                """
                Sends a message to the websocket server.

                :returns: A deferred that will be called when the associated response comes back.

                .. note::
                    Only one message can be sent at a time at the moment.
                """
                super(ClientProtocol, self).sendMessage(payload, isBinary=is_binary)
                self._on_message_deferred = Deferred()
                return self._on_message_deferred

            def _get_deferred(self):
                """
                Retrieves the current deferred and clears it from the client.
                """
                d = self._on_message_deferred
                self._on_message_deferred = None
                return d

            def onMessage(self, payload, is_binary):
                """
                Invokes any callback attached to the last Deferred returned by sendMessage.
                """
                self._get_deferred().callback(payload)

            def onClose(self, was_clean, code, reason):
                # Only report clean closure, since they are the ones initiated by the server.
                if was_clean:
                    self._get_deferred().callback((code, reason))

        # Create the websocket connection to the server.
        self._port = port
        client_factory = WebSocketClientFactory(
            "wss://shotgunlocalhost.com:%s" % self._port
        )
        client_factory.origin = origin
        client_factory.protocol = ClientProtocol
        self.client = connectWS(client_factory, context_factory, timeout=2)

        # When the test ends, we need to stop listening.
        self.addCleanup(lambda: self.client.disconnect())
        self.addCleanup(lambda: self.server._observer.stop())
        self.addCleanup(lambda: self.server.listener.stopListening())

        # Return the deferred that will be called then the setup is completed.
        return connection_ready_deferred

    def _call_rpc(self, name, paylad, *args):
        """
        Implements the retrieval of the websocket server secret.
        """
        if name == "retrieve_ws_server_secret":
            return {"ws_server_secret": self._ws_server_secret}
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
            method = calls.pop(0)
            d = method(payload)

            # If we got a Deferred back
            if d and len(calls) == 0:
                # Make sure there are more calls to make
                done.errback(RuntimeError("Got a Deferred, but call chain is empty."))
            elif not d and len(calls) != 0:
                # If we don't have a deferred as a result, simply call the next method.
                self._call_next(None, calls, done)
                return

            # If a deferred is returned, we must invoke the remaining calls when the deferred
            # is signaled.
            if d:
                d.addCallback(lambda payload: self._call_next(payload, calls, done))
            else:
                # We didn't get a Deferred and it was the last method, so invoke the done deferred
                # to tell the test case we're done.
                done.callback(None)
        except Exception as e:
            # There was an error, abort the test right now!
            done.errback(e)

    def _send_payload(self, payload, encrypt=False, is_binary=False):
        """
        Sends a payload as is to the server.
        """
        if encrypt:
            payload = self._fernet.encrypt(payload)
        return self.client_protocol.sendMessage(payload, is_binary)

    def _send_message(
        self,
        command,
        data,
        encrypt=False,
        is_binary=False,
        protocol_version=2,
        user_id=None,
    ):
        """
        Sends a message to the websocket server in the expected format.
        """
        payload = {
            "id": 1,
            "protocol_version": protocol_version,
            "command": {
                "name": command,
                "data": {"user": {"entity": {"id": user_id or self._user["id"]}}},
            },
        }
        if data:
            payload["command"]["data"].update(data)
        return self._send_payload(json.dumps(payload), encrypt=encrypt)

    def _is_error(self, payload, msg):
        """
        Asserts if a payload is an error message.
        """
        self.assertEqual(payload.get("error", False), True)
        self.assertTrue(
            payload["error_message"].startswith(msg),
            "'%s' does not start with '%s'" % (payload["error_message"], msg),
        )

    def _is_not_error(self, payload):
        self.assertNotIn("error", payload)

    def _activate_encryption_if_required(self, _):
        """
        Activate encryption if this test suite needs it.
        """
        if self._use_encryption:
            return self._activate_encryption(_)
        else:
            return None

    def _activate_encryption(self, _):
        """
        Activates encryption
        """
        return self._send_message("get_ws_server_id", None)


def CommonTestsMetaClass(class_name, class_parents, class_attr):
    def register(func):
        class_attr[func.__name__] = func

    # These are tests that are common to encryped and unenrypted servers.
    @register
    def test_connecting(self):
        """
        Makes sure our unit tests framework can connect
        """
        self.assertEqual(self.client.state, "connected")

    @register
    def test_websocket_with_unknown_intermediate_chain(self):
        """
        Make sure we can connect to the site.
        """
        # The websocket connection in the websocket module, contrary to Twisted's implementation,
        # requires the entire certificate chain to be available to connect to shotgunlocalhost.com
        # So we'll use that to validate that the cert chain is passed entirely on connection.
        return threads.deferToThread(
            lambda: websocket.create_connection(
                "wss://shotgunlocalhost.com:%s" % self._port
            ).close()
        )

    @register
    def test_binary_unsupported(self):
        """
        Makes sure any payload is rejected if it is sent in binary form.
        """

        def step1(_):
            return self._send_payload("not_valid_command", is_binary=True)

        def step2(payload):
            payload = json.loads(payload)
            self._is_error(payload, "Server does not handle binary requests.")

        return self._chain_calls(step1, step2)

    @register
    def test_invalid_protocol_version(self):
        """
        Ensures invalid protocol versions are caught.
        """

        def step1(_):
            return self._send_message(
                "repeat_value", {"value": "hello"}, protocol_version=-1
            )

        def step2(payload):
            payload = json.loads(payload)
            self._is_error(payload, "Unsupported protocol version: -1.")

        return self._chain_calls(step1, step2)

    @register
    def test_incorrectly_formatted_json(self):
        """
        Ensures incorrectly formatted json gets caught.
        """

        def step1(_):
            return self._send_payload("{'allo':}")

        def step2(payload):
            payload = json.loads(payload)
            self._is_error(payload, "Error in decoding the message's json data")

        return self._chain_calls(step1, step2)

    @register
    def test_missing_user(self):
        """
        Ensures that if the user is missing from a command that the command will be rejected
        accordingly.
        """

        def step1(_):
            return self._send_payload(
                json.dumps(
                    {
                        "id": 1,
                        "protocol_version": 2,
                        "command": {"name": "repeat_value", "data": {"value": "hello"}},
                    }
                ),
                encrypt=self._use_encryption,
            )

        def step2(payload):
            self.assertEqual(
                payload, (3000, "No user information was found in this request.")
            )

        return self._chain_calls(self._activate_encryption_if_required, step1, step2)

    @register
    def test_incorrect_user(self):
        """
        Ensure incorrect user is caught
        """

        def step1(_):
            return self._send_message(
                "repeat_value",
                {"value": "hello"},
                encrypt=self._use_encryption,
                user_id=666,
            )

        def step2(payload):
            self.assertEqual(
                payload,
                (
                    3001,
                    "You are not authorized to make browser integration requests. "
                    "Please re-authenticate in your desktop application.",
                ),
            )

        return self._chain_calls(self._activate_encryption_if_required, step1, step2)

    @register
    def test_unknown_command(self):
        """
        Ensures that a method that is not in the supported list raises an error.
        """

        def step1(_):
            return self._send_message(
                "unknown_command", None, encrypt=self._use_encryption
            )

        def step2(payload):
            if self._use_encryption:
                payload = self._fernet.decrypt(payload)
            payload = json.loads(payload)
            self._is_error(payload, "Command unknown_command is not supported.")

        return self._chain_calls(self._activate_encryption_if_required, step1, step2)

    @register
    def test_missing_method(self):
        """
        Ensures a public method that has a missing matching attribute raises an error.
        """

        def step1(_):
            return self._send_message(
                "missing_attribute", None, encrypt=self._use_encryption
            )

        def step2(payload):
            if self._use_encryption:
                payload = self._fernet.decrypt(payload)
            payload = json.loads(payload)
            self._is_error(payload, "Could not find API method missing_attribute: ")

        return self._chain_calls(self._activate_encryption_if_required, step1, step2)

    return type(class_name, class_parents, class_attr)


class TestEncryptedServer(TestServerBase):
    """
    Tests for various caching-related methods for api_v2.
    """

    __metaclass__ = CommonTestsMetaClass

    def setUp(self):
        super(TestEncryptedServer, self).setUp()
        return self.setUpClientServer(use_encryption=True)

    def test_calls_encrypted(self):
        """
        Ensures that calls are encrypted after get_ws_server_is is invoked.
        """

        def step1(payload):
            return self._send_message("repeat_value", {"value": "hello"}, encrypt=True)

        def step2(payload):
            payload = self._fernet.decrypt(payload)
            payload = json.loads(payload)
            self._is_not_error(payload)
            self.assertEqual(payload["reply"]["value"], "hellohellohello")

            # Same call without encryption should fail.
            return self._send_message("repeat_value", {"value": "hello"})

        def step3(payload):
            payload = self._fernet.decrypt(payload)
            payload = json.loads(payload)
            self._is_error(payload, "There was an error while decrypting the message:")

        return self._chain_calls(self._activate_encryption, step1, step2, step3)

    def test_rpc_before_encrypt(self):
        """
        Calling an RPC before doing the encryption handshake should not work.
        """

        def step1(payload):
            return self._send_message("repeat_value", None)

        def step2(payload):
            self.assertEqual(
                payload,
                (
                    3002,
                    "Attempted to communicate without completing encryption handshake.",
                ),
            )

        return self._chain_calls(step1, step2)


class TestUnencryptedServer(TestServerBase):
    """
    Tests for various caching-related methods for api_v2.
    """

    __metaclass__ = CommonTestsMetaClass

    def setUp(self):
        super(TestUnencryptedServer, self).setUp()
        return self.setUpClientServer(use_encryption=False)

    def test_get_ws_server_id_failure(self):
        """
        Ensures get_ws_server_id does not work when not in encryption mode.
        """

        def step1(_):
            return self._send_message("get_ws_server_id", None)

        def step2(payload):
            self.assertEqual(
                payload,
                (3003, "Client asked for server id when encryption is not supported."),
            )

        return self._chain_calls(step1, step2)


class DifferentHostBase(object):
    """
    Tests a connection from a different host. The server needs to be launched in different modes,
    but this can only be done during setUp due to the way twisted unit tests work.

    In order to have the unit test be parameterizable, the base class will expect class level
    variables to be set that indicate if encryption is required or not, what are the aliases
    and if the test should fail or not.
    """

    class Impl(TestServerBase):
        def setUp(self):
            super(DifferentHostBase.Impl, self).setUp()
            print((self.__class__))
            return self.setUpClientServer(
                use_encryption=self.use_encryption,
                origin=self.origin,
                host_aliases=self.host_aliases,
            )

        def test_origin(self):
            def step_send_message(payload):
                return self._send_message(
                    "repeat_value", {"value": "hello"}, encrypt=self._use_encryption
                )

            def step_failure(payload):
                self.assertEqual(
                    payload,
                    (
                        3001,
                        "You are not authorized to make browser integration "
                        "requests. Please re-authenticate in your desktop application.",
                    ),
                )

            def step_validation(payload):
                if self.should_fail:
                    step_failure(payload)
                else:
                    self.assertFalse(isinstance(payload, tuple))

                    if self.use_encryption:
                        payload = self._fernet.decrypt(payload)

                    payload = json.loads(payload)
                    self.assertEqual(payload["reply"], {"value": "hellohellohello"})

            # When using encryption, we won't even be able to enable it because we'll
            # be on the wrong side. So move straight away to the failure step.
            if self._use_encryption and self.should_fail:
                return self._chain_calls(
                    self._activate_encryption_if_required, step_failure
                )
            else:
                return self._chain_calls(
                    self._activate_encryption_if_required,
                    step_send_message,
                    step_validation,
                )


class TestInvalidOriginEncrypted(DifferentHostBase.Impl):
    """
    Make sure that a different origin will fail when encryption is on.
    """

    should_fail = True
    use_encryption = True
    origin = "https://altsite.shotgunstudio.com"
    host_aliases = []


class TestInvalidOriginUnencrypted(TestInvalidOriginEncrypted):
    """
    Make sure that a different origin will fail when encryption is off
    """

    use_encryption = False


class TestValidOriginEncrypted(DifferentHostBase.Impl):
    """
    Make sure that using an alias will succeed when encryption is on.
    """

    should_fail = False
    use_encryption = True
    origin = "https://altsite.shotgunstudio.com"
    host_aliases = ["altsite.shotgunstudio.com"]


class TestValidOriginUnencrypted(TestValidOriginEncrypted):
    """
    Make sure that using an alias will succeed when encryption is off.
    """

    use_encryption = False

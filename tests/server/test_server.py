# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import base64
import contextlib
import datetime
import http.client
import json
import os
import shutil
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import websocket
from tank_test.tank_test_base import setUpModule  # noqa

import sgtk
from tank_vendor.shotgun_api3.lib.mockgun import Shotgun

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
fixtures_root = os.path.join(repo_root, "tests", "fixtures")

sys.path.insert(0, os.path.join(repo_root, "python"))

# Mock Qt since we don't have it.
sgtk.platform.qt.QtCore = Mock()
sgtk.platform.qt.QtGui = Mock()

# Doing this import will add the bundled libraries.
import tk_framework_desktopserver  # noqa

from cryptography import x509  # noqa
from cryptography.fernet import Fernet  # noqa
from cryptography.hazmat.primitives import hashes, serialization  # noqa
from cryptography.hazmat.primitives.asymmetric import ec  # noqa
from cryptography.x509.oid import NameOID  # noqa

# Default for ``_send_message``'s ``user_id``: send the authenticated user's id. A
# sentinel is used so tests can send explicit falsy ids such as 0 or None (null).
AUTHENTICATED_USER = object()

HOSTNAME = "shotgunlocalhost.com"

UNAUTHORIZED_USER = (
    3001,
    "You are not authorized to make browser integration requests. "
    "Please re-authenticate in your desktop application.",
)


def find_free_port():
    """
    Finds a free port on the current computer.
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def create_certificates(folder):
    """
    Creates a root certificate authority, an intermediate one and a server
    certificate signed by the intermediate one.

    Writes server.crt, holding the server and intermediate certificates, and
    server.key to the folder, like the shotgunlocalhost certificates.

    :returns: Path to the root certificate, which clients must trust.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    def create(name, issuer_name, issuer_key, is_ca):
        key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            x509.CertificateBuilder()
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)])
            )
            .not_valid_after(now + datetime.timedelta(days=1))
            .not_valid_before(now - datetime.timedelta(days=1))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .add_extension(
                x509.BasicConstraints(ca=is_ca, path_length=None), critical=True
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    (issuer_key or key).public_key()
                ),
                critical=False,
            )
        )
        if is_ca:
            builder = builder.add_extension(
                x509.KeyUsage(
                    content_commitment=False,
                    crl_sign=True,
                    data_encipherment=False,
                    decipher_only=False,
                    digital_signature=True,
                    encipher_only=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    key_encipherment=False,
                ),
                critical=True,
            )
        else:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False
            )
        certificate = builder.sign(issuer_key or key, hashes.SHA256())
        return certificate, key

    root, root_key = create("Test root", "Test root", None, True)
    intermediate, intermediate_key = create(
        "Test intermediate", "Test root", root_key, True
    )
    server, server_key = create(HOSTNAME, "Test intermediate", intermediate_key, False)

    def pem(certificate):
        return certificate.public_bytes(serialization.Encoding.PEM)

    with open(os.path.join(folder, "root.crt"), "wb") as f:
        f.write(pem(root))
    with open(os.path.join(folder, "server.crt"), "wb") as f:
        f.write(pem(server) + pem(intermediate))
    with open(os.path.join(folder, "server.key"), "wb") as f:
        f.write(
            server_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    return os.path.join(folder, "root.crt")


class MockShotgunApi(object):
    """
    Mocks the v2 protocol with custom methods.
    """

    PUBLIC_API_METHODS = ["missing_attribute", "repeat_value", "wait"]

    # Set to let the wait commands return.
    release = threading.Event()
    # Set when a wait command started.
    started = threading.Event()
    # Thread that ran the last wait command.
    wait_thread = None

    def __init__(self, host, process_manager, wss_key):
        self._host = host

    def repeat_value(self, payload):
        self._host.reply({"value": payload["value"] * 3})

    def wait(self, payload):
        MockShotgunApi.wait_thread = threading.current_thread()
        self.started.set()
        self.release.wait(30)
        self._host.reply({"value": "done"})


class TestServerBase(unittest.TestCase):
    """
    Starts a server and connects a client to it.
    """

    origin = "https://site.shotgunstudio.com"
    host_aliases = ["site.shotgunstudio.com"]
    use_encryption = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._keys_path = tempfile.mkdtemp()
        cls._root_certificate = create_certificates(cls._keys_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._keys_path)
        super().tearDownClass()

    def setUp(self):
        super().setUp()

        # Create a mockgun instance and add support for the _call_rpc method, which
        # is used to get the secret.
        Shotgun.set_schema_paths(
            os.path.join(fixtures_root, "mockgun", "schema.pickle"),
            os.path.join(fixtures_root, "mockgun", "schema_entity.pickle"),
        )
        self._mockgun = Shotgun("https://127.0.0.1")
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
        self._patch(
            "sgtk.platform.current_bundle", return_value=Mock(shotgun=self._mockgun)
        )

        from tk_framework_desktopserver import Server, shotgun

        self._patch.object(Server, "Notifier", new=Mock())
        self._patch.object(
            shotgun,
            "get_shotgun_api",
            new=lambda _, host, process_manager, wss_key: MockShotgunApi(
                host, process_manager, wss_key
            ),
        )

        MockShotgunApi.release.clear()
        MockShotgunApi.started.clear()
        self.addCleanup(MockShotgunApi.release.set)

        self._port = find_free_port()
        self.server = Server(
            keys_path=self._keys_path,
            encrypt=self.use_encryption,
            host="https://site.shotgunstudio.com",
            user_id=self._user["id"],
            host_aliases=self.host_aliases,
            port=self._port,
            uses_intermediate_certificate_chain=True,
        )
        self.server.start()
        self.addCleanup(self.server.tear_down)

        self.client = self._connect()

    @property
    def _patch(self):
        """
        Starts a patch and stops it when the test ends. Use like
        :func:`unittest.mock.patch`.
        """

        def start(patcher):
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            return mock

        def patch_target(*args, **kwargs):
            return start(patch(*args, **kwargs))

        patch_target.object = lambda *args, **kwargs: start(
            patch.object(*args, **kwargs)
        )
        return patch_target

    def _call_rpc(self, name, payload, *args):
        """
        Implements the retrieval of the websocket server secret.
        """
        if name == "retrieve_ws_server_secret":
            return {"ws_server_secret": self._ws_server_secret}
        else:
            raise NotImplementedError("The RPC %s is not implemented." % name)

    def _connect(self, **kwargs):
        """
        Connects a client to the server. The client only trusts the root
        certificate, so the server must send the intermediate one.
        """
        client = websocket.create_connection(
            "wss://127.0.0.1:%d" % self._port,
            origin=self.origin,
            sslopt={
                "ca_certs": self._root_certificate,
                "server_hostname": HOSTNAME,
            },
            timeout=5,
            **kwargs
        )
        self.addCleanup(client.close)
        return client

    def _https_get(self, path):
        """
        Sends a plain HTTPS GET request to the server.

        :returns: The :class:`http.client.HTTPResponse`, with its body read.
        """
        context = ssl.create_default_context(cafile=self._root_certificate)
        context.check_hostname = False
        connection = http.client.HTTPSConnection(
            "127.0.0.1", self._port, context=context, timeout=5
        )
        self.addCleanup(connection.close)
        connection.request("GET", path)
        response = connection.getresponse()
        response.body = response.read().decode("utf-8")
        return response

    def _receive(self, client=None):
        """
        Receives the next message.

        :returns: The text of a message, or a (code, reason) tuple when the server
            closes the connection.
        """
        client = client or self.client
        opcode, frame = client.recv_data_frame(True)
        if opcode == websocket.ABNF.OPCODE_CLOSE:
            # websocket-client answers the close frame but keeps the TCP
            # connection open. Close it, as browsers do, so the server doesn't
            # wait for it.
            client.shutdown()
            code = struct.unpack("!H", frame.data[:2])[0]
            return (code, frame.data[2:].decode("utf-8"))
        # Replies must be text, as the web app expects.
        self.assertEqual(opcode, websocket.ABNF.OPCODE_TEXT)
        return frame.data.decode("utf-8")

    def _receive_json(self, client=None):
        """
        Receives the next message, decrypting it when encryption is on.

        :returns: The decoded JSON payload.
        """
        payload = self._receive(client)
        if self._fernet_active:
            payload = self._fernet.decrypt(payload.encode("utf-8"))
        return json.loads(payload)

    _fernet_active = False

    def _send_payload(self, payload, encrypt=False, is_binary=False, client=None):
        """
        Sends a payload as is to the server.
        """
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if encrypt:
            payload = self._fernet.encrypt(payload)
        opcode = (
            websocket.ABNF.OPCODE_BINARY if is_binary else websocket.ABNF.OPCODE_TEXT
        )
        (client or self.client).send(payload, opcode)

    def _send_message(
        self,
        command,
        data,
        encrypt=False,
        protocol_version=2,
        user_id=AUTHENTICATED_USER,
        client=None,
    ):
        """
        Sends a message to the websocket server in the expected format.

        :param user_id: Id of the user sending the request. Defaults to the
            authenticated user. Any other value, including 0 and None, is sent as is.
        """
        if user_id is AUTHENTICATED_USER:
            user_id = self._user["id"]
        payload = {
            "id": 1,
            "protocol_version": protocol_version,
            "command": {
                "name": command,
                "data": {"user": {"entity": {"id": user_id}}},
            },
        }
        if data:
            payload["command"]["data"].update(data)
        self._send_payload(json.dumps(payload), encrypt=encrypt, client=client)

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

    def _activate_encryption_if_required(self):
        """
        Activate encryption if this test suite needs it.
        """
        if self.use_encryption:
            self._activate_encryption()

    def _activate_encryption(self):
        """
        Activates encryption.
        """
        self._send_message("get_ws_server_id", None)
        payload = json.loads(self._receive())
        self.assertEqual(payload["reply"]["ws_server_id"], self.server.ws_server_id)
        self._fernet_active = True


class CommonTests(object):
    """
    Tests common to encrypted and unencrypted servers.
    """

    def test_binary_unsupported(self):
        """
        Makes sure any payload is rejected if it is sent in binary form.
        """
        self._send_payload("not_valid_command", is_binary=True)
        self._is_error(
            json.loads(self._receive()), "Server does not handle binary requests."
        )

    def test_compression_declined(self):
        """
        Makes sure the server declines permessage-deflate, like autobahn did.
        """
        client = self._connect(header=["Sec-WebSocket-Extensions: permessage-deflate"])
        self.assertNotIn("sec-websocket-extensions", client.getheaders())

    def test_concurrent_requests(self):
        """
        Makes sure replies sent at the same time from the request threads all
        arrive.
        """
        self._activate_encryption_if_required()
        for i in range(50):
            self._send_message(
                "repeat_value", {"value": str(i)}, encrypt=self.use_encryption
            )
        values = sorted(self._receive_json()["reply"]["value"] for _ in range(50))
        self.assertEqual(values, sorted(str(i) * 3 for i in range(50)))

    def test_connecting(self):
        """
        Makes sure our unit tests framework can connect.
        """
        self.assertTrue(self.client.connected)

    def test_incorrect_user(self):
        """
        Ensure incorrect user is caught.
        """
        self._activate_encryption_if_required()
        self._send_message(
            "repeat_value", {"value": "hello"}, encrypt=self.use_encryption, user_id=666
        )
        self.assertEqual(self._receive(), UNAUTHORIZED_USER)
        self.server.notifier.different_user_requested.emit.assert_called_once_with(
            self.origin, 666
        )

    def test_incorrectly_formatted_json(self):
        """
        Ensures incorrectly formatted json gets caught.
        """
        self._send_payload("{'allo':}")
        self._is_error(
            json.loads(self._receive()), "Error in decoding the message's json data"
        )

    def test_invalid_protocol_version(self):
        """
        Ensures invalid protocol versions are caught.
        """
        self._send_message("repeat_value", {"value": "hello"}, protocol_version=-1)
        self._is_error(json.loads(self._receive()), "Unsupported protocol version: -1.")

    def test_listens_on_loopback_only(self):
        """
        Makes sure other computers can't reach the server.
        """
        self.assertEqual(
            self.server._websocket_server.socket.getsockname()[0], "127.0.0.1"
        )

    def test_missing_method(self):
        """
        Ensures a public method that has a missing matching attribute raises an error.
        """
        self._activate_encryption_if_required()
        self._send_message("missing_attribute", None, encrypt=self.use_encryption)
        self._is_error(
            self._receive_json(), "Could not find API method missing_attribute: "
        )

    def test_missing_user(self):
        """
        Ensures that if the user is missing from a command that the command will be
        rejected accordingly.
        """
        self._activate_encryption_if_required()
        self._send_payload(
            json.dumps(
                {
                    "id": 1,
                    "protocol_version": 2,
                    "command": {"name": "repeat_value", "data": {"value": "hello"}},
                }
            ),
            encrypt=self.use_encryption,
        )
        self.assertEqual(
            self._receive(), (3000, "No user information was found in this request.")
        )

    def test_null_user(self):
        """
        Ensures a request with a null user id is rejected.
        """
        self._assert_unauthorized_user(None)

    def test_oversize_message(self):
        """
        Makes sure messages over 1 MiB, the websockets default, close the
        connection with code 1009 (message too big).
        """
        self._send_payload("x" * (2**20 + 1))
        self.assertEqual(self._receive()[0], 1009)

    def test_port_busy(self):
        """
        Makes sure a second server on the same port fails with PortBusyError.
        """
        from tk_framework_desktopserver import PortBusyError, Server

        server = Server(
            keys_path=self._keys_path,
            encrypt=self.use_encryption,
            host="https://site.shotgunstudio.com",
            user_id=self._user["id"],
            host_aliases=self.host_aliases,
            port=self._port,
        )
        with self.assertRaises(PortBusyError):
            server.start()

    def test_protocol_v1_rejected(self):
        """
        Ensures protocol v1 requests, which carry no user id, are rejected as an
        unsupported protocol version, even from an allowed origin.
        """
        self._activate_encryption_if_required()
        self._send_message(
            "repeat_value",
            {"value": "hello"},
            encrypt=self.use_encryption,
            protocol_version=1,
        )
        self._is_error(self._receive_json(), "Unsupported protocol version: 1.")

    def test_redirect(self):
        """
        Makes sure ?redirect= redirects right away.
        """
        response = self._https_get(
            "/?redirect=https%3A%2F%2Fsite.shotgunstudio.com%2Fpage%3Fa%3D1"
        )
        self.assertEqual(response.status, 303)
        self.assertEqual(
            response.getheader("Location"), "https://site.shotgunstudio.com/page?a=1"
        )

    def test_redirect_after(self):
        """
        Makes sure &after= redirects from the status page after a delay.
        """
        response = self._https_get(
            "/?redirect=https%3A%2F%2Fsite.shotgunstudio.com%2F&after=3"
        )
        self.assertEqual(response.status, 200)
        self.assertIn(
            '<meta http-equiv="refresh" content="3;URL=\'https://site.shotgunstudio.com/\'">',
            response.body,
        )

    def test_redirect_escaped(self):
        """
        Makes sure a redirect url can't add headers or HTML.
        """
        response = self._https_get(
            "/?redirect=https%3A%2F%2Fsite%0D%0AX-Injected%3A%201%22%3E"
        )
        self.assertEqual(response.status, 303)
        self.assertIsNone(response.getheader("X-Injected"))
        self.assertEqual(
            response.getheader("Location"), "https://site%0D%0AX-Injected:%201%22%3E"
        )

        response = self._https_get(
            "/?redirect=https%3A%2F%2Fsite%27%3E%3Cscript%3E&after=0"
        )
        self.assertNotIn("<script>", response.body)

    def test_restart(self):
        """
        Makes sure the server can be started again after tear_down.
        """
        self.client.close()
        self.server.tear_down()
        self.assertFalse(self.server.is_running())
        self.server.start()
        self.assertTrue(self.server.is_running())
        client = self._connect()
        self._send_message(
            "repeat_value", {"value": "hello"}, protocol_version=-1, client=client
        )
        self._is_error(
            json.loads(self._receive(client)), "Unsupported protocol version: -1."
        )

    def test_shutdown_with_requests_running(self):
        """
        Makes sure tear_down closes connections with code 1001 and doesn't wait
        for running requests.
        """
        self._activate_encryption_if_required()
        self._send_message("wait", None, encrypt=self.use_encryption)
        self.assertTrue(MockShotgunApi.started.wait(5))
        # Python doesn't wait for daemon threads at exit, so Desktop can quit.
        self.assertTrue(MockShotgunApi.wait_thread.daemon)

        # Like a browser, answer the closing handshake while tear_down runs.
        received = []
        reader = threading.Thread(target=lambda: received.append(self._receive()))
        reader.start()

        start = time.monotonic()
        self.server.tear_down()
        self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(self.server.is_running())
        reader.join(5)
        self.assertEqual(received, [(1001, "")])

        # The request finishes after the connection closed. Its reply is dropped.
        MockShotgunApi.release.set()

    def test_status_page(self):
        """
        Makes sure a plain HTTPS GET serves the status page.
        """
        response = self._https_get("/")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
        self.assertIn("Flow Production Tracking browser integration", response.body)
        self.assertNotIn("http-equiv", response.body)

    def test_unknown_command(self):
        """
        Ensures that a method that is not in the supported list raises an error.
        """
        self._activate_encryption_if_required()
        self._send_message("unknown_command", None, encrypt=self.use_encryption)
        self._is_error(
            self._receive_json(), "Command unknown_command is not supported."
        )

    def test_websocket_with_unknown_intermediate_chain(self):
        """
        Makes sure the server sends the intermediate certificate. Clients only
        trust the root certificate, so the connection fails otherwise.
        """
        client = self._connect()
        self.assertTrue(client.connected)

        # Without the root certificate, the connection fails.
        with self.assertRaises(ssl.SSLError):
            websocket.create_connection(
                "wss://127.0.0.1:%d" % self._port,
                sslopt={"server_hostname": HOSTNAME},
                timeout=5,
            )

    def test_zero_user(self):
        """
        Ensures a request with a user id of 0 is rejected.
        """
        self._assert_unauthorized_user(0)

    def _assert_unauthorized_user(self, user_id):
        """
        Sends a request with the given user id and ensures the server closes the
        connection as unauthorized, before dispatching the command.

        :param user_id: Id of the user sending the request.
        """
        self._activate_encryption_if_required()
        self._send_message(
            "repeat_value",
            {"value": "hello"},
            encrypt=self.use_encryption,
            user_id=user_id,
        )
        self.assertEqual(self._receive(), UNAUTHORIZED_USER)


class TestEncryptedServer(CommonTests, TestServerBase):
    """
    Tests the server when encryption is on.
    """

    use_encryption = True

    def test_calls_encrypted(self):
        """
        Ensures that calls are encrypted after get_ws_server_id is invoked.
        """
        self._activate_encryption()
        self._send_message("repeat_value", {"value": "hello"}, encrypt=True)
        payload = self._receive_json()
        self._is_not_error(payload)
        self.assertEqual(payload["reply"]["value"], "hellohellohello")

        # Same call without encryption should fail.
        self._send_message("repeat_value", {"value": "hello"})
        self._is_error(
            self._receive_json(), "There was an error while decrypting the message:"
        )

    def test_rpc_before_encrypt(self):
        """
        Calling an RPC before doing the encryption handshake should not work.
        """
        self._send_message("repeat_value", None)
        self.assertEqual(
            self._receive(),
            (3002, "Attempted to communicate without completing encryption handshake."),
        )


class TestUnencryptedServer(CommonTests, TestServerBase):
    """
    Tests the server when encryption is off.
    """

    use_encryption = False

    def test_get_ws_server_id_failure(self):
        """
        Ensures get_ws_server_id does not work when not in encryption mode.
        """
        self._send_message("get_ws_server_id", None)
        self.assertEqual(
            self._receive(),
            (3003, "Client asked for server id when encryption is not supported."),
        )


class DifferentHostTests(object):
    """
    Tests a connection from a different host. Subclasses set whether encryption
    is on, the origin, the aliases and whether the request should fail.
    """

    def test_origin(self):
        if self.use_encryption and self.should_fail:
            # When using encryption, we won't even be able to enable it because we'll
            # be on the wrong side.
            self._send_message("get_ws_server_id", None)
            self.assertEqual(self._receive(), UNAUTHORIZED_USER)
            return

        self._activate_encryption_if_required()
        self._send_message(
            "repeat_value", {"value": "hello"}, encrypt=self.use_encryption
        )
        if self.should_fail:
            self.assertEqual(self._receive(), UNAUTHORIZED_USER)
        else:
            self.assertEqual(
                self._receive_json()["reply"], {"value": "hellohellohello"}
            )


class TestInvalidOriginEncrypted(DifferentHostTests, TestServerBase):
    """
    Make sure that a different origin will fail when encryption is on.
    """

    host_aliases = ["site.shotgunstudio.com"]
    origin = "https://altsite.shotgunstudio.com"
    should_fail = True
    use_encryption = True


class TestInvalidOriginUnencrypted(TestInvalidOriginEncrypted):
    """
    Make sure that a different origin will fail when encryption is off.
    """

    use_encryption = False


class TestValidOriginEncrypted(DifferentHostTests, TestServerBase):
    """
    Make sure that using an alias will succeed when encryption is on.
    """

    host_aliases = ["altsite.shotgunstudio.com"]
    origin = "https://altsite.shotgunstudio.com"
    should_fail = False
    use_encryption = True


class TestValidOriginUnencrypted(TestValidOriginEncrypted):
    """
    Make sure that using an alias will succeed when encryption is off.
    """

    use_encryption = False

# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import base64
import html
import http
import os
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, quote, urlparse

from sgtk.platform.qt import QtCore
from websockets.sync.server import serve

from . import certificates
from .errors import MissingCertificateError, PortBusyError
from .logger import get_logger
from .server_protocol import ServerProtocol

logger = get_logger(__name__)

# Reasons OpenSSL gives when the browser rejects the certificate during the TLS
# handshake.
_CERTIFICATE_ERROR_REASONS = frozenset(
    [
        "SSLV3_ALERT_BAD_CERTIFICATE",
        "SSLV3_ALERT_CERTIFICATE_UNKNOWN",
        "SSLV3_ALERT_HANDSHAKE_FAILURE",
        "TLSV1_ALERT_UNKNOWN_CA",
    ]
)

# Page served on a plain HTTPS GET, for example when the user opens the server
# in a browser tab to accept its certificate.
_STATUS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
   <head>
      {redirect}
      <title>Flow Production Tracking browser integration</title>
   </head>
   <body>
      <h1>Flow Production Tracking browser integration</h1>
      <p>
         This is not a web server, but a <b>WebSocket</b> endpoint.
      </p>
   </body>
</html>
"""

# Characters left unescaped in a redirect URL: the reserved and unreserved
# characters of RFC 3986, plus "%" to keep existing escapes.
_URL_SAFE_CHARACTERS = "!#$%&'()*+,/:;=?@[]~"


class _LoggingSSLSocket(ssl.SSLSocket):
    """
    Logs why a TLS handshake failed, so certificate errors show in the logs.
    """

    def do_handshake(self, *args, **kwargs):
        """
        Performs the TLS handshake and logs any failure before raising it.
        """
        try:
            super().do_handshake(*args, **kwargs)
        except ssl.SSLError as e:
            # Firefox and Safari send an alert when they reject the certificate.
            # Chrome drops the connection instead, which looks like an EOF.
            if isinstance(e, ssl.SSLEOFError) or e.reason in _CERTIFICATE_ERROR_REASONS:
                logger.info("Certificate error!")
            else:
                logger.info("TLS handshake failed.")
            logger.debug("Reason received for connection loss: %s", e)
            raise
        except ConnectionResetError as e:
            logger.info("Certificate error!")
            logger.debug("Reason received for connection loss: %s", e)
            raise
        except OSError as e:
            logger.info("Connection closed.")
            logger.debug("Reason received for connection loss: %s", e)
            raise


class Server(object):
    _DEFAULT_PORT = 9000
    _DEFAULT_KEYS_PATH = "../resources/keys"

    # Only accept connections from this computer.
    _LISTEN_HOST = "127.0.0.1"

    # Number of requests processed at the same time, as with the Twisted thread
    # pool this replaces.
    _MAX_WORKERS = 10

    # Close code sent to browsers when the server stops.
    _GOING_AWAY = 1001

    # Seconds tear_down waits for connections to close and for the server thread
    # to finish.
    _SHUTDOWN_TIMEOUT = 5

    class Notifier(QtCore.QObject):
        different_user_requested = QtCore.Signal(str, int)

    def __init__(
        self,
        keys_path,
        encrypt,
        host,
        user_id,
        host_aliases,
        port=None,
        uses_intermediate_certificate_chain=False,
    ):
        """
        Constructor.

        :param keys_path: Path to the keys. If the path is relative, it will be relative to the
            current working directory. Mandatory
        :param encrypt: If True, the communication with clients will be encrypted.
        :param host: Url of the host we're expecting requests from.
        :param user_id: Id of the user we're expecting requests from.
        :param host_aliases: List of aliases available for the current host.
        :param port: Port to listen for websocket requests from.
        :param uses_intermediate_certificate_chain: Unused, kept for compatibility.
            The server always serves every certificate in the certificate file.
        """
        self._port = port or self._DEFAULT_PORT
        self._keys_path = keys_path or self._DEFAULT_KEYS_PATH
        self._host = host
        self._user_id = user_id
        self._host_aliases = host_aliases
        self._uses_intermediate_certificate_chain = uses_intermediate_certificate_chain

        # Open connections, closed by tear_down. websockets only tracks them from
        # version 17.0.
        self._closing = False
        self._connections = set()
        self._connections_lock = threading.Lock()
        self._executor = None
        self._server_thread = None
        self._websocket_server = None

        # If encryption is required, compute a server id and retrieve the secret associated to it.
        if encrypt:
            # urandom is considered cryptographically secure as it calls the OS's CSRNG, so we can
            # use that to generate our own server id.
            self._ws_server_id = base64.urlsafe_b64encode(os.urandom(16)).decode(
                "utf-8"
            )
        else:
            self._ws_server_id = None

        self.notifier = self.Notifier()

        if not os.path.exists(keys_path):
            raise MissingCertificateError(keys_path)

        logger.debug("Browser integration using certificates at %s", self._keys_path)
        logger.debug("Encryption: %s", encrypt)

    @property
    def host(self):
        """
        :returns: Url of the host we're expecting requests from.
        """
        return self._host

    @property
    def host_aliases(self):
        """
        :returns: List of aliases available for the current host.
        """
        return self._host_aliases

    @property
    def user_id(self):
        """
        :returns: Id of the user we're expecting requests from.
        """
        return self._user_id

    @property
    def ws_server_id(self):
        """
        :returns: Id of the server when encryption is required, ``None`` otherwise.
        """
        return self._ws_server_id

    def get_logger(self):
        """
        :returns: The python logger root for the framework.
        """
        return logger

    def is_running(self):
        """
        :returns: True if the server is up and running, False otherwise.
        """
        return self._server_thread is not None and self._server_thread.is_alive()

    def start(self):
        """
        Start shotgun web server, listening to websocket connections.
        """
        self._start_server()
        self._start_server_thread()

    def submit(self, func, *args):
        """
        Runs a request in the thread pool.

        :param func: Function to call.
        :param args: Arguments to pass to the function.
        """
        future = self._executor.submit(func, *args)
        future.add_done_callback(self._log_request_failure)

    def tear_down(self):
        """
        Stops the server. It can be started again afterwards.

        Closes connections with code 1001 (going away). Does not wait for running
        requests: their replies are dropped. Waits at most a few seconds for
        clients to acknowledge the close.
        """
        if self._websocket_server:
            # Shut down from another thread, so a client that doesn't answer the
            # closing handshake can't block the caller.
            shutdown_thread = threading.Thread(
                args=(self._websocket_server,),
                daemon=True,
                name="desktopserver-shutdown",
                target=self._close_connections,
            )
            shutdown_thread.start()
            shutdown_thread.join(self._SHUTDOWN_TIMEOUT)
            if shutdown_thread.is_alive():
                logger.warning("Timed out while closing browser connections.")
            self._websocket_server = None

        if self._executor:
            self._executor.shutdown(cancel_futures=True, wait=False)
            self._executor = None

        if self._server_thread:
            self._server_thread.join(self._SHUTDOWN_TIMEOUT)
            if self._server_thread.is_alive():
                logger.warning("The browser integration server did not stop.")
            self._server_thread = None

    def _close_connections(self, websocket_server):
        """
        Stops accepting connections and closes open ones with code 1001.

        :param websocket_server: The websockets ``Server``.
        """
        with self._connections_lock:
            self._closing = True
            connections = list(self._connections)

        # Close in parallel: each close waits for the browser to answer.
        threads = [
            threading.Thread(
                args=(self._GOING_AWAY,),
                daemon=True,
                name="desktopserver-close",
                target=connection.close,
            )
            for connection in connections
        ]
        for thread in threads:
            thread.start()

        # From websockets 17.0, this also waits for connection handlers to finish.
        websocket_server.shutdown()

        for thread in threads:
            thread.join()

    def _create_ssl_context(self, cert_crt_path, cert_key_path):
        """
        Creates the TLS context of the server.

        :param cert_crt_path: Path to the certificate file. Every certificate in the
            file is sent to the client, so it can hold an intermediate chain.
        :param cert_key_path: Path to the private key file.

        :returns: The :class:`ssl.SSLContext`.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_crt_path, cert_key_path)
        context.sslsocket_class = _LoggingSSLSocket
        return context

    def _handle_connection(self, connection):
        """
        Handles a websocket connection until it closes. Called from a thread
        websockets creates for each connection.

        :param connection: The websockets ``ServerConnection``.
        """
        with self._connections_lock:
            closing = self._closing
            if not closing:
                self._connections.add(connection)

        # The connection opened while tear_down was closing the others.
        if closing:
            connection.close(self._GOING_AWAY)
            return

        try:
            ServerProtocol(self, connection).run()
        finally:
            with self._connections_lock:
                self._connections.discard(connection)

    def _log_request_failure(self, future):
        """
        Logs any exception that escaped a request.

        :param future: :class:`concurrent.futures.Future` of the request.
        """
        if not future.cancelled() and future.exception():
            logger.error(
                "Unexpected error while processing a request:",
                exc_info=future.exception(),
            )

    def _process_request(self, connection, request):
        """
        Answers plain HTTPS requests, which don't ask for a websocket upgrade.

        Serves a status page. With ``?redirect=<url>``, redirects to the url right
        away, or after a number of seconds with ``&after=<seconds>``.

        :param connection: The websockets ``ServerConnection``.
        :param request: The websockets ``Request``.

        :returns: The response to send, or ``None`` to open the websocket.
        """
        if "Upgrade" in request.headers:
            return None

        params = parse_qs(urlparse(request.path).query)
        redirect_url = params.get("redirect", [""])[0]
        if not redirect_url:
            return self._status_page_response(connection)

        redirect_url = quote(redirect_url, safe=_URL_SAFE_CHARACTERS)
        try:
            after = int(params["after"][0])
        except (KeyError, ValueError):
            response = connection.respond(http.HTTPStatus.SEE_OTHER, "")
            response.headers["Location"] = redirect_url
            return response

        return self._status_page_response(
            connection,
            '<meta http-equiv="refresh" content="%d;URL=\'%s\'">'
            % (after, html.escape(redirect_url)),
        )

    def _raise_if_missing_certificate(self, certificate_path):
        """
        Raises an exception is a certificate file is missing.

        :param certificate_path: Path to the certificate file.

        :raises Exception: Thrown if the certificate file is missing.
        """
        if not os.path.exists(certificate_path):
            raise MissingCertificateError(
                "Missing certificate file: %s" % certificate_path
            )

    def _start_server(self):
        """
        Start shotgun web server, listening to websocket connections.

        :raises PortBusyError: Thrown if the port is already in use.
        """
        cert_crt_path, cert_key_path = certificates.get_certificate_file_names(
            self._keys_path
        )

        self._raise_if_missing_certificate(cert_key_path)
        self._raise_if_missing_certificate(cert_crt_path)

        with self._connections_lock:
            self._closing = False

        ssl_context = self._create_ssl_context(cert_crt_path, cert_key_path)

        try:
            self._websocket_server = serve(
                self._handle_connection,
                self._LISTEN_HOST,
                self._port,
                # Browsers offer permessage-deflate. Decline it, as autobahn did.
                compression=None,
                logger=get_logger("websockets"),
                process_request=self._process_request,
                ssl=ssl_context,
            )
        except OSError as e:
            raise PortBusyError(str(e))

        self._executor = ThreadPoolExecutor(
            max_workers=self._MAX_WORKERS,
            thread_name_prefix="desktopserver-request",
        )

    def _start_server_thread(self):
        """
        Serves connections from a Python thread.
        """
        self._server_thread = threading.Thread(
            daemon=True,
            name="desktopserver",
            target=self._websocket_server.serve_forever,
        )
        self._server_thread.start()

    def _status_page_response(self, connection, redirect=""):
        """
        Builds the status page response.

        :param connection: The websockets ``ServerConnection``.
        :param redirect: HTML to add to the page head, to redirect the browser.

        :returns: The websockets ``Response``.
        """
        response = connection.respond(
            http.HTTPStatus.OK, _STATUS_PAGE_TEMPLATE.format(redirect=redirect)
        )
        del response.headers["Content-Type"]
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response

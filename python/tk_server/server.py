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
import os
import threading

from server_protocol import ServerProtocol
from status_server_protocol import StatusServerProtocol

from twisted.internet import reactor, ssl
from twisted.python import log

from autobahn.twisted.websocket import WebSocketServerFactory, listenWS

class Server:
    _DEFAULT_PORT = 9000
    _DEFAULT_PORT_STATUS = 9001

    def _start_status_server(self, debug):
        """
        not-secure server that is used to report errors (such as invalid certificate) and validate that server exists.

        :param debug: bool
        """
        if debug:
            log.startLogging(sys.stdout)

        ws_port = os.environ.get("TANK_PORT_STATUS", Server._DEFAULT_PORT_STATUS)

        factory = WebSocketServerFactory("ws://localhost:%d" % ws_port, debug=debug, debugCodePaths=debug)

        factory.protocol = StatusServerProtocol
        factory.setProtocolOptions(allowHixie76=True, echoCloseCodeReason=True)
        listener = listenWS(factory)

    def _start_server(self, debug=False, keys_path="resources/keys"):
        """
        Start shotgun web server, listening to websocket connections.

        :param debug: Boolean Show debug output. Will also Start local web server to test client pages.
        """

        ws_port = os.environ.get("TANK_PORT", Server._DEFAULT_PORT)
        keys_path = os.environ.get("TANK_DESKTOP_CERTIFICATE", keys_path)

        cert_key_path = os.path.join(keys_path, "server.key")
        cert_crt_path = os.path.join(keys_path, "server.crt")

        if not os.path.exists(cert_crt_path) or not os.path.exists(cert_key_path):
            StatusServerProtocol.serverStatus = StatusServerProtocol.SSL_NO_CERTIFICATE_FILE
            return

        # SSL server context: load server key and certificate
        self.context_factory = ssl.DefaultOpenSSLContextFactory(cert_key_path,
                                                                cert_crt_path)

        self.factory = WebSocketServerFactory("wss://localhost:%d" % ws_port, debug=debug, debugCodePaths=debug)

        self.factory.protocol = ServerProtocol
        self.factory.setProtocolOptions(allowHixie76=True, echoCloseCodeReason=True)
        self.listener = listenWS(self.factory, self.context_factory)

    def start(self, debug=False, keys_path="resources/keys", start_reactor=False):
        """
        Start shotgun web server, listening to websocket connections.

        :param debug: Boolean Show debug output. Will also Start local web server to test client pages.
        :param keys_path: Path to the certificate files (.crt and .key).
        :param start_reactor: Boolean Start threaded reactor
        """
        if debug:
            log.startLogging(sys.stdout)

        self._start_server(debug, keys_path)
        self._start_status_server(debug)

        if start_reactor:
            def start():
                reactor.run(installSignalHandlers=0)

            t = threading.Thread(target=start)
            t.start()

    def stop(self):
        reactor.callFromThread(reactor.stop)

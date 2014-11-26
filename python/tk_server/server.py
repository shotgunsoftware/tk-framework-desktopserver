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

from server_protocol import *

from twisted.internet import reactor, ssl
from twisted.python import log

from autobahn.twisted.websocket import WebSocketServerFactory, listenWS

DEFAULT_PORT = 9000


class Server:

    def start(self, debug=False, keys_path="resources/keys"):
        """
        Start shotgun web server, listening to websocket connections.

        :param debug: Boolean Show debug output. Will also Start local web server to test client pages.
        """

        if debug:
            log.startLogging(sys.stdout)

        ws_port = os.environ.get("TANK_PORT", DEFAULT_PORT)

        ## SSL server context: load server key and certificate
        ## We use this for both WS and Web!
        ##
        self.contextFactory = ssl.DefaultOpenSSLContextFactory(os.path.join(keys_path, "server.key"),
                                                               os.path.join(keys_path, "server.crt"))

        factory = WebSocketServerFactory("wss://localhost:%d" % ws_port,
                                         debug = debug,
                                         debugCodePaths = debug)

        factory.protocol = ServerProtocol
        factory.setProtocolOptions(allowHixie76 = True)
        listenWS(factory, self.contextFactory)

        # Keep application alive
        reactor.run()

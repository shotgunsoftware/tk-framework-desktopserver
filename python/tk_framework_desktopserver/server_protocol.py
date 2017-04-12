# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import json
import re
import datetime
from urlparse import urlparse
import OpenSSL
import threading

from .shotgun import get_shotgun_api
from .message_host import MessageHost
from .status_server_protocol import StatusServerProtocol
from .process_manager import ProcessManager
from .logger import get_logger

from autobahn import websocket
from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import error, reactor


class ServerProtocol(WebSocketServerProtocol):
    """
    Server Protocol
    """

    # Initial state is v2. This might change if we end up receiving a connection
    # from a client at v1.
    PROTOCOL_VERSION = 2
    SUPPORTED_PROTOCOL_VERSIONS = (1, 2)

    def __init__(self):
        self._logger = get_logger()
        self.process_manager = ProcessManager.create()
        self._semaphore = threading.Semaphore()

    def onClose(self, wasClean, code, reason):
        pass

    def connectionLost(self, reason):
        """
        Called when connection is lost

        :param reason: Object Reason for connection lost
        """
        try:
            # Known certificate error. These work for firefox and safari, but chrome rejected certificate
            # are currently indistinguishable from lost connection. This is true as of July 21st, 2015.
            certificate_error = False
            certificate_error |= reason.type is OpenSSL.SSL.Error and reason.value.message[0][2] == 'ssl handshake failure'
            certificate_error |= reason.type is OpenSSL.SSL.Error and reason.value.message[0][2] == 'tlsv1 alert unknown ca'
            certificate_error |= bool(reason.check(error.CertificateError))

            if certificate_error:
                self._logger.info("Certificate error!")
                StatusServerProtocol.serverStatus = StatusServerProtocol.SSL_CERTIFICATE_INVALID
            else:
                self._logger.info("Connection closed.")
                StatusServerProtocol.serverStatus = StatusServerProtocol.CONNECTION_LOST
        except Exception:
            self._logger.exception("Unexpected error while losing connection.")
            StatusServerProtocol.serverStatus = StatusServerProtocol.CONNECTION_LOST

    def onConnect(self, response):
        """
        Called upon client connection to server. This is where we decide if we accept the connection
        or refuse it based on domain origin filtering.

        :param response: Object Response information.
        """

        # If we reach this point, then it means SSL handshake went well..
        StatusServerProtocol.serverStatus = StatusServerProtocol.CONNECTED

        domain_valid = False
        try:
            # response.origin: xyz.shotgunstudio.com
            domain_valid = self._is_domain_valid(response.origin)
        except:
            self._logger.exception("Unexpected error while trying to determine the originating domain.")

        if not domain_valid:
            self._logger.info("Invalid domain: %s" % response.origin)
            # Don't accept connection
            raise websocket.http.HttpException(403, "Domain origin was rejected by server.")
        else:
            self._logger.info("Connection accepted.")
            self._wss_key = response.headers["sec-websocket-key"]

    def onMessage(self, payload, isBinary):
        """
        Called by 'WebSocketServerProtocol' when we receive a message from the websocket

        Entry point into our Shotgun API.

        :param payload: String Message payload
        :param isBinary: If the message is in binary format
        """

        # We don't currently handle any binary messages
        if isBinary:
            return

        decoded_payload = payload.decode("utf8")
        # Special message to get protocol version for this protocol. This message doesn't follow the standard
        # message format as it doesn't require a protocol version to be retrieved and is not json-encoded.
        if decoded_payload == "get_protocol_version":
            self.json_reply(dict(protocol_version=self.PROTOCOL_VERSION))
            return

        # Extract json response (every message is expected to be in json format)
        try:
            message = json.loads(decoded_payload)
        except ValueError, e:
            self.report_error("Error in decoding the message's json data: %s" % e.message)
            return

        message_host = MessageHost(self, message)

        # Check protocol version
        if message["protocol_version"] not in self.SUPPORTED_PROTOCOL_VERSIONS:
            message_host.report_error(
                "Unsupported protocol version: %s " % message["protocol_version"]
            )
            return

        # TODO: This isn't going to work if we have two different clients
        # connecting at two different protocol versions. This is a temp
        # hack to placate message_host.py. <jbee>
        self.PROTOCOL_VERSION = message["protocol_version"]

        # Run each request from a thread, even though it might be something very simple like opening a file. This
        # will ensure the server is as responsive as possible. Twisted will take care of the thread.
        reactor.callInThread(
            self._process_message,
            message_host,
            message,
            message["protocol_version"],
        )

    def _process_message(self, message_host, message, protocol_version):

        # Retrieve command from message
        command = message["command"]

        # Retrieve command data from message
        data = command.get("data", dict())
        cmd_name = command["name"]

        # Create API for this message
        try:
            # Do not resolve to simply ShotgunAPI in the imports, this allows tests to mock errors
            api = get_shotgun_api(
                protocol_version,
                message_host,
                self.process_manager,
                wss_key=self._wss_key,
            )
        except Exception, e:
            message_host.report_error("Unable to get a ShotgunAPI object: %s" % e)
            return

        # Make sure the command is in the public API
        if cmd_name in api.PUBLIC_API_METHODS:
            # Call matching shotgun command
            try:
                func = getattr(api, cmd_name)
                requires_sync = (cmd_name in api.SYNCHRONOUS_METHODS)
            except Exception, e:
                message_host.report_error(
                    "Could not find API method %s: %s" % (cmd_name, e)
                )
            else:
                # If a method is expecting to be run synchronously we
                # need to make sure that happens. An example of this is
                # the get_actions method in v2 of the api, which might
                # trigger a cache update. If that happens, we can't let
                # multiple cache processes occur at once, because each
                # is bootstrapping sgtk, which won't play well if multiple
                # are occurring at the same time, all of which potentially
                # copying/downloading files to disk in the same location.
                if requires_sync:
                    self._semaphore.acquire()
                try:
                    func(data)
                except Exception, e:
                    import traceback
                    message_host.report_error(
                        "Method call failed for %s: %s" % (cmd_name, traceback.format_exc())
                    )
                finally:
                    if requires_sync:
                        self._semaphore.release()
        else:
            message_host.report_error("Command %s is not supported." % cmd_name)

    def report_error(self, message, data=None):
        """
        Report an error to the client.
        Note: The error has no message id and therefore will lack traceability in the client.

        :param message: String Message describing the error.
        :param data: Object Optional Additional information regarding the error.
        """
        error = {}
        error["error"] = True
        if data:
            error["error_data"] = data
        error["error_message"] = message

        # Log error to console
        self._logger.warning("Error in reply: " + message)

        self.json_reply(error)

    def json_reply(self, data):
        """
        Send a JSON-formatted message to client.

        :param data: Object Data that will be converted to JSON and sent to client.
        """
        # ensure_ascii allows unicode strings.
        payload = json.dumps(data, ensure_ascii=False, default=self._json_date_handler).encode("utf8")

        is_binary = False
        self.sendMessage(payload, is_binary)

    def _wildcard_match(self, wildcard, match):
        """
        Matches a string that may contain wildcard (*) with another string.

        :param wildcard: String that may contain wildcards
        :param match: String to match with.
        :return: True if there is a match, False otherwise
        """

        #
        # Make a regex with wildcard string by substituting every '*' with .* and make sure to keep '.' intact.
        #    ex: from *.shotgunstudios.com   -->   '.*(\\.shotgunstudios\\.com)$'

        # Regex string to build
        expr_str = ""

        wildcard_tokens = wildcard.split("*")
        for i in range(0, len(wildcard_tokens)):
            token = wildcard_tokens[i]

            # Make token regex literal (we want to keep '.' for instance)
            literal = "(" + re.escape(token) + ")"

            expr_str += literal

            if i >= (len(wildcard_tokens) - 1):
                # Make sure there can't be any other character at the end
                expr_str += "$"
            else:
                expr_str += ".*"

        # Match regexp
        exp = re.compile(expr_str, re.IGNORECASE)
        match = exp.match(match)

        if match:
            return True
        else:
            return False

    def _is_domain_valid(self, origin_str):
        """
        Filters for valid origin domain names.

        :param origin_str: Domain origin string (ex: http://localhost:8080)
        :return: True if domain is accepted, False otherwise
        """
        domain_env = os.environ.get("SHOTGUN_PLUGIN_DOMAIN_RESTRICTION", self.factory.websocket_server_whitelist)

        origin = urlparse(origin_str)

        # split domain on commas
        domain_match = False
        domains = domain_env.split(",")
        for domain in domains:
            domain = domain.strip()

            domain_match = self._wildcard_match(domain, origin.hostname)
            if domain_match:
                break

        return domain_match

    def _json_date_handler(self, obj):
        """
        JSON stringify python date handler from: http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript
        :returns: return a serializable version of obj or raise TypeError
        :raises: TypeError if a serializable version of the object cannot be made
        """
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder().default(obj)

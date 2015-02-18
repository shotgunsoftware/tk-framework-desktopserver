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

from shotgun_api import ShotgunAPI
from message_host import MessageHost
from status_server_protocol import StatusServerProtocol

from autobahn import websocket
from autobahn.twisted.websocket import WebSocketServerProtocol

DEFAULT_DOMAIN_RESTRICTION = "*.shotgunstudio.com,localhost"


class ServerProtocol(WebSocketServerProtocol):
    """
    Server Protocol
    """

    # Server protocol version
    protocol_version = 1

    def __init__(self):
        """
        Server Protocol constructor
        """
        pass

    def onClose(self, wasClean, code, reason):
        pass

    def connectionLost(self, reason):
        """
        Called when connection is lost

        :param reason: Object Reason for connection lost
        """
        try:
            if reason.value.message[0][2] == 'ssl handshake failure':
                StatusServerProtocol.serverStatus = StatusServerProtocol.SSL_CERTIFICATE_INVALID
            else:
                StatusServerProtocol.serverStatus = StatusServerProtocol.OK
        except Exception, e:
            StatusServerProtocol.serverStatus = StatusServerProtocol.OK

    def onConnect(self, response):
        """
        Called upon client connection to server. This is where we decide if we accept the connection
        or refuse it based on domain origin filtering.

        :param response: Object Response information.
        """

        # If we reach this point, then it means SSL handshake went well..
        StatusServerProtocol.serverStatus = StatusServerProtocol.OK

        domain_valid = False
        try:
            # response.origin: http://localhost:8080
            origin_str = response.origin

            # No origin would be a local html file
            origin_localhost = response.host == "localhost" or origin_str == "file://"
            if origin_localhost:
                origin_str = "http://localhost"
            else:
                raise Exception("Invalid or unknown origin.")

            domain_valid = ServerProtocol.domain_filter(origin_str)
        except Exception as e:
            # Otherwise errors get swallowed by outer blocks
            print "Domain validation failed: ", e.message

        if not domain_valid:
            # Don't accept connection
            raise websocket.http.HttpException(403, "Domain origin was rejected by server.")

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
            data = {}
            data["protocol_version"] = self.protocol_version
            self.json_reply(data)
            return

        # Extract json response (every message is expected to be in json format)
        try:
            message = json.loads(decoded_payload)
        except ValueError, e:
            self.report_error("Error in decoding the message's json data: " + e.message)
            return

        message_host = MessageHost(self, message)

        # Check protocol version
        if message["protocol_version"] != self.protocol_version:
            message_host.report_error("Error. Wrong protocol version [{version}] ".format(version=self.protocol_version))
            return

        # Retrieve command from message
        command = message["command"]

        # Retrieve command data from message
        data = {}
        if "data" in command:
            data = command["data"]

        cmd_name = command["name"]

        # Create API for this message
        try:
            shotgun = ShotgunAPI(message_host)
        except Exception as e:
            message_host.report_error("Error in loading ShotgunAPI. " + e.message)
            return

        # Make sure the command is in the public API
        if cmd_name in shotgun.public_api:
            # Call matching shotgun command
            func = getattr(shotgun, cmd_name)
            func(data)
        else:
            message_host.report_error("Error! Wrong Command Sent: [%s]" % cmd_name)

    def report_error(self, message, data=None):
        """
        Report an error to the client.
        Note: The error has no message id and therefore will lack traceability in the client.

        :param message: String Message describing the error.
        :param data: Object Optional Additional information regarding the error.
        """
        error = {}
        error["error"] = True
        if data: error["error_data"] = data
        error["error_message"] = message

        # Log error to console
        print "Error in reply: " + message

        self.json_reply(error)

    def json_reply(self, data):
        """
        Send a JSON-formatted message to client.

        :param data: Object Data that will be converted to JSON and sent to client.
        """
        # ensure_ascii allows unicode strings.
        payload = json.dumps(data, ensure_ascii=False, default=self._json_date_handler).encode("utf8")

        isBinary = False
        self.sendMessage(payload, isBinary)

    @staticmethod
    def wildcard_match(wildcard, match):
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


    @staticmethod
    def domain_filter(origin_str):
        """
        Filters for valid origin domain names.

        :param origin_str: Domain origin string (ex: http://localhost:8080)
        :return: True if domain is accepted, False otherwise
        """
        domain_env = os.environ.get("SHOTGUN_PLUGIN_DOMAIN_RESTRICTION", DEFAULT_DOMAIN_RESTRICTION)

        origin = urlparse(origin_str)

        # split domain on commas
        domain_match = False
        domains = domain_env.split(",")
        for domain in domains:
            domain = domain.strip()

            domain_match = ServerProtocol.wildcard_match(domain, origin.hostname)
            if domain_match:
                break

        return domain_match

    @staticmethod
    def _json_date_handler(obj):
        """
        JSON stringify python date handler from: http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript
        """
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, datetime.datetime):
            return isinstance(obj, datetime.datetime)
        else:
            raise TypeError, 'Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj))

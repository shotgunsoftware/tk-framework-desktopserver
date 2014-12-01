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

from urlparse import urlparse

from shotgun_api import ShotgunAPI

from autobahn import websocket
from autobahn.twisted.websocket import WebSocketServerProtocol

DEFAULT_DOMAIN_RESTRICTION = '*.shotgunstudio.com,localhost'


class ServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        self.shotgun = ShotgunAPI(self)

    def onConnect(self, response):
        """
        Called upon client connection to server. This is where we decide if we accept the connection
        or refuse it based on domain origin filtering.

        :param response: Object Response information.
        """

        domain_valid = False
        try:
            # response.origin: http://localhost:8080
            origin_str = response.origin

            # No origin would be a local html file
            if (origin_str == 'null' and response.host == 'localhost') or (origin_str == "file://"):
                origin_str = "http://localhost"
            else:
                raise Exception("Invalid or unknown origin.")

            domain_valid = ServerProtocol.domain_filter(origin_str)
        except Exception as e:
            # Otherwise errors get swallowed by outer blocks
            print "Domain validation failed: ", e.message

        if not domain_valid:
            # Don't accept connection
            raise websocket.http.HttpException(403, 'Domain origin was rejected by server.')

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

        # Process json response (every message is expected to be in json format)
        command = json.loads(payload.decode('utf8'))
        data = {}

        # Retrieve command data from message
        if 'data' in command:
            data = command['data']

        cmd_name = command['name']

        # Make sure the command is in the public API
        if cmd_name in self.shotgun.public_api:
            # Call matching shotgun command
            func = getattr(self.shotgun, cmd_name)
            func(data)
        else:
            self.report_error("Error! Wrong Command Sent: [%s]" % cmd_name)

    def report_error(self, message, data=None):
        """
        Report an error to the client.

        :param message: String Message describing the error.
        :param data: Object Optional Additional information regarding the error.
        """
        error = {}
        error['error'] = True
        if data: error['error_data'] = data
        error['error_message'] = message

        self.json_reply(error)

    def json_reply(self, data):
        """
        Send a JSON-formatted message to client.

        :param data: Object Data that will be converted to JSON and sent to client.
        """
        # ensure_ascii allows unicode strings.
        payload = json.dumps(data, ensure_ascii = False).encode('utf8')

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
        expr_str = ''

        wildcard_tokens = wildcard.split('*')
        for token in wildcard_tokens:
            # Make token regex literal (we want to keep '.' for instance)
            literal = '(' + re.escape(token) + ')'

            expr_str += literal

            if token is not wildcard_tokens[-1]:
                expr_str += '.*'
            else:
                # Make sure there can't be any other character at the end
                expr_str += "$"

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
        domains = domain_env.split(',')
        for domain in domains:
            domain = domain.strip()

            domain_match = ServerProtocol.wildcard_match(domain, origin.hostname)
            if domain_match:
                break

        return domain_match


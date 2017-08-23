# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import datetime

import OpenSSL
from cryptography.fernet import Fernet
from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import error, reactor

import sgtk

from .shotgun import get_shotgun_api
from .message_host import MessageHost
from .process_manager import ProcessManager
from .message import Message
from .logger import get_logger

logger = get_logger(__name__)


class ServerProtocol(WebSocketServerProtocol):
    """
    Server Protocol
    """

    (
        USER_INFO_NOT_FOUND,
        UNAUTHORIZED_USER,
        ENCRYPTION_HANDSHAKE_NOT_COMPLETED,
        ENCRYPTION_NOT_SUPPORTED
    ) = (
        (
            3000,
            u"No user information was found in this request."
        ),
        (
            3001,
            u"You are not authorized to make browser integration requests. "
            u"Please re-authenticate in your desktop application."
        ),
        (
            3002,
            u"Attempted to communicate without encryption enabled."
        ),
        (
            3003,
            u"Client asked for server id when encryption is not supported."
        )
    )

    # Initial state is v2. This might change if we end up receiving a connection
    # from a client at v1.
    SUPPORTED_PROTOCOL_VERSIONS = (1, 2)

    # Cached result of the server secret retrieval
    _ws_server_secret = None

    def __init__(self):
        super(WebSocketServerProtocol, self).__init__()
        self._process_manager = ProcessManager.create()
        self._protocol_version = 2
        # When set, the message to and from the server will be encrypted.
        self._fernet = None

    @property
    def process_manager(self):
        """
        The protocol handler's associated process manager object.
        """
        return self._process_manager

    @property
    def protocol_version(self):
        """
        The protocol handler's currently-supported protocol version.
        """
        return self._protocol_version

    def connectionLost(self, reason):
        """
        Called when connection is lost

        :param reason: Object Reason for connection lost
        """
        try:
            # Known certificate error. These work for firefox and safari, but chrome rejected certificate
            # are currently indistinguishable from lost connection. This is true as of July 21st, 2015.
            certificate_error = False
            certificate_error |= (
                reason.type is OpenSSL.SSL.Error and
                reason.value.message[0][2] == 'ssl handshake failure'
            )
            certificate_error |= (
                reason.type is OpenSSL.SSL.Error and
                reason.value.message[0][2] == 'tlsv1 alert unknown ca'
            )
            certificate_error |= bool(reason.check(error.CertificateError))

            if certificate_error:
                logger.info("Certificate error!")
            else:
                logger.info("Connection closed.")
        except Exception:
            logger.exception("Unexpected error while losing connection.")

        logger.debug("Reason received for connection loss: %s", reason)

    def onConnect(self, response):
        """
        Called upon client connection to server. This is where we decide if we accept the connection
        or refuse it based on domain origin.

        :param response: Object Response information.
        """
        # If we reach this point, then it means SSL handshake went well..
        self._origin = response.origin.lower()
        logger.info("Connection accepted.")
        self._wss_key = response.headers["sec-websocket-key"]

    def onMessage(self, payload, is_binary):
        """
        Called by 'WebSocketServerProtocol' when we receive a message from the websocket

        Entry point into our Shotgun API.

        :param payload: String Message payload
        :param isBinary: If the message is in binary format
        """

        # We don't currently handle any binary messages
        if is_binary:
            self.report_error("Server does not handle binary requests.")
            return

        if self._fernet:
            try:
                payload = self._fernet.decrypt(payload)
            except Exception as e:
                self.report_error("There was an error while decrypting the message: %s" % e.message)
                logger.exception("Unexpected error while decrypting:")
                return

        decoded_payload = payload.decode("utf8")

        # Special message to get protocol version for this protocol. This message doesn't follow the
        # standard message format as it doesn't require a protocol version to be retrieved and is
        # not json-encoded.
        if decoded_payload == "get_protocol_version":
            self.json_reply(dict(protocol_version=self._protocol_version))
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

        self._protocol_version = message["protocol_version"]

        if message["command"]["name"] == "get_ws_server_id":
            self._handle_get_ws_server_id(message)
            return

        # Make sure that nothing gets replied to when encryption is required until the server knows
        # the public server id and we've turned on encryption by initializing the Fernet instance.
        if self._is_using_encryption() and not self._fernet:
            message_host.report_error("Attempting to communicate without encryption enabled.")
            self.sendClose(**self.ENCRYPTION_HANDSHAKE_NOT_COMPLETED)
            return

        # origin is formatted such as https://xyz.shotgunstudio.com:port_number
        # host is https://xyz.shotgunstudio.com:port_number
        origin_network = self._origin.lower()
        host_network = self.factory.host.lower()

        if self._protocol_version == 2:
            # Version 2 of the protocol can only answer requests from the site and user the server
            # is authenticated into. Validate this.

            # Try to get the user information. If that fails, we need to report the error.
            try:
                user_id = message["command"]["data"]["user"]["entity"]["id"]
            except Exception:
                logger.exception("Unexpected error while trying to retrieve the user id.")
                self.sendClose(**self.USER_INFO_NOT_FOUND)
                return
        else:
            user_id = None

        # If the hosts are different or the user ids are different, report an error.
        if host_network != origin_network or (user_id is not None and user_id != self.factory.user_id):
            logger.debug("Browser integration request received a different user.")
            logger.debug("Desktop site: %s", host_network)
            logger.debug("Desktop user: %s", self.factory.user_id)
            logger.debug("Origin site: %s", origin_network)
            logger.debug("Origin user: %s", user_id)
            self.factory.notifier.different_user_requested.emit(self._origin, user_id)
            self.sendClose(**self.UNAUTHORIZED_USER)
            return

        # Run each request from a thread, even though it might be something very simple like opening
        # a file. This will ensure the server is as responsive as possible. Twisted will take care
        # of the thread.
        reactor.callInThread(
            self._process_message,
            message_host,
            message,
            message["protocol_version"],
        )

    def _is_using_encryption(self):
        """
        Checks if this connection requires encryption.

        .. note::
            While the connection requires encryption, it doesn't necessarily mean that encryption
            is active on the connection. The initial handshake between the client and the server
            when requesting for the server id is unencrypted.

        :returns: True if this connection will require encryption.
        """
        return True if self.factory.ws_server_id else False

    def _handle_get_ws_server_id(self, message):
        """
        Handles the request for the server id.

        This method will retrieve the websocket server secret and send back the server id to the
        webapp.
        """

        if not self._is_using_encryption():
            self.sendClose(**self.ENCRYPTION_NOT_SUPPORTED)
            return

        # Build a response for the web app.
        message = Message(message["id"], self._protocol_version)
        message.reply({
            "ws_server_id": self.factory.ws_server_id
        })

        # send the response.
        self.json_reply(message.data)

        # Create a Fernet instance so we can start encrypting and decrypting messages from now on.
        self._fernet = Fernet(self._retrieve_server_secret())

    def _retrieve_server_secret(self):
        """
        Retrieves the server secret from Shotgun.

        .. note::
            This method caches the result of the retrieval for any other ServerProtocol instances
            created after the first one.

            Because
                - each server instance has a different server id
                - retrieving a secret with a different id generates a new secret
                - we can launch two servers at the same time (the second one won't be able to listen
                  and will fail however.)
            , it wouldn't be a good idea to retrieve the server id before successfully listening
            on the port since launching the server a second time by mistake would reset the secret
            retrieved by the first instance.
        """
        # Has the server secret already been retrieved before?
        if not self._ws_server_secret:
            # Ask for the secret for this server id.
            shotgun = sgtk.platform.current_engine().shotgun
            # FIXME: Make this method public on the Shotgun API.
            response = shotgun._call_rpc(
                "retrieve_ws_server_secret", {"ws_server_id": self.factory.ws_server_id}
            )
            ws_server_secret = response["ws_server_secret"]
            # FIXME: Server doesn't seem to provide a properly padded string. The Javascript side
            # doesn't seem to complain however, so I'm not sure whose implementation is broken.
            if ws_server_secret[-1] != "=":
                ws_server_secret += "="

            self._ws_server_secret = ws_server_secret

        return self._ws_server_secret

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
                try:
                    func(data)
                except Exception, e:
                    import traceback
                    message_host.report_error(
                        "Method call failed for %s: %s" % (cmd_name, traceback.format_exc())
                    )
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
        logger.warning("Error in reply: " + message)

        self.json_reply(error)

    def json_reply(self, data):
        """
        Send a JSON-formatted message to client.

        :param data: Object Data that will be converted to JSON and sent to client.
        """
        # ensure_ascii allows unicode strings.
        payload = json.dumps(
            data,
            ensure_ascii=False,
            default=self._json_date_handler,
        ).encode("utf8")

        if self._fernet:
            payload = self._fernet.encrypt(payload)
        self.sendMessage(payload, False)

    def _json_date_handler(self, obj):
        """
        JSON stringify python date handler from:
        http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript
        :returns: return a serializable version of obj or raise TypeError
        :raises: TypeError if a serializable version of the object cannot be made
        """
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder().default(obj)

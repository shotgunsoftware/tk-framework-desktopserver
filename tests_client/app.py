# -*- coding: utf-8 -*-

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

if __name__ == '__main__':
    """
    Simple application for client/server development and testing.

    Example usage: python app.py debug

    Server TODO:
        - Test on all Platforms
            - Dependencies:
                [cryptography, cffi, six, pycparser]
                [service-identity, pyasn1, pyasn1-modules, pyopens, sl, characteristic]   --> service_identity for test_client only?

            - General issues with test client
                - pip install service-identity
            - Linux issues
                For cffi:
                    yum install libffi-devel
                    yum install python-devel
                    yum install openssl-devel
                    pip install cffi
                - When do we actually need both files/folder selection?
        - uft-8 unit testing internationalization
            - Internationalization works fine, except for this case: /Users/rivestm/tmp 普通话/ 國語/ 華語.txt, were filename is
              'tmp 普通话/ 國語/ 華語.txt'. The '/' should be encoded by the client differently, and possibly decoded
              differently on the server too.
        - To remove the annoying "allow connection" dialog when starting the server, use:
            to sign: codesign -f -s <certname> /path/to/app --deep
                 or: codesign --force --deep --sign - /Applications/Shotgun.app (doesn't seem to work with bundle)
            to verify: codesign -vvv /Applications/Shotgun.app
    """
    sys.path.append("../")

    from python.tk_server import Server

    from twisted.internet import reactor, ssl
    from twisted.web.static import File
    from twisted.web.server import Site
    from twisted.python import log


    # Get debug info
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug = True
    else:
        debug = False

    if debug:
        log.startLogging(sys.stdout)

    server = Server()

    # Serve test pages
    local_server = debug
    keys_folder = "../resources/keys"
    if local_server:
        # Serve client folder
        keys_dir = File(keys_folder)
        web_dir = File("./client")
        web_dir.putChild("keys", keys_dir)
        web_dir.contentTypes[".crt"] = "application/x-x509-ca-cert"
        web = Site(web_dir)
        #reactor.listenSSL(8080, web, server.contextFactory)        # For serving https..
        reactor.listenTCP(8080, web)

    server.start(debug, keys_folder)

    # Keep application alive
    reactor.run()

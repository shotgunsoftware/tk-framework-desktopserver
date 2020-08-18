# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank_test.tank_test_base import setUpModule, interactive
from base_test import TestDesktopServerFramework

import pytest

skip_on_ci = pytest.mark.skipif("CI" in os.environ, reason="These tests require manual intervention to execute.")

class TestCertificates(TestDesktopServerFramework):

    @skip_on_ci
    def test_certificate_creation_flow(self):
        """
        Ensure certificates registration and creation work.
        """
        # Get the certificate handle. We pass in the current test's temporary folder
        # for the location of the cert, which means they do not exist at the moment.
        handler = self.framework_module.certificates.get_certificate_handler(self.tank_temp)

        # Because certs are registered at the OS level, we need to unregister them first
        # for this test to pass. Unfortunately, this pre-supposes that is_registered and
        # unregister actually work in the first place for the rest of the test to work.
        if handler.is_registered():
            handler.unregister()

        # Make sure the certificates are nowhere on disk. That's expected
        # as we're working from tank_temp.
        assert handler.exists() is False
        # No cert should be registered with the OS now.
        assert handler.is_registered() is False
        # Let's create the certs and make sure they are now on disk
        handler.create()
        assert handler.exists()
        # However, they should not be registered with the OS at the moment
        assert handler.is_registered() is False
        # Now register them
        handler.register()
        # and they should be registered.
        assert handler.is_registered()
        # Now we unregister with the OS.
        handler.unregister()
        # It should still exist on disk...
        assert handler.exists()
        # ...but not be registered with the OS.
        assert handler.is_registered() is False
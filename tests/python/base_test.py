# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys

from tank_test.tank_test_base import TankTestBase, setUpModule
import sgtk
from mock_test_classes import MockHost, MockConfigDescriptor

class TestDesktopServerFramework(TankTestBase):
    def setUp(self):
        super(TestDesktopServerFramework, self).setUp()
        self.setup_fixtures()

        # set up an environment variable that points to the root of the
        # framework so we can specify its location in the environment fixture

        self.framework_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        os.environ["FRAMEWORK_ROOT"] = self.framework_root

        # We're not going to be adding tests for the legacy workaround, so we
        # will disable it.
        #
        # TODO: This can be removed once the legacy workaround is gone. <jbee>
        os.environ["SGTK_DISABLE_LEGACY_BROWSER_INTEGRATION_WORKAROUND"] = "1"

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.project])

        # run folder creation for the shot
        self.tk.create_filesystem_structure(self.project["type"], self.project["id"])

        # now make a context
        context = self.tk.context_from_entity(self.project["type"], self.project["id"])

        # and start the engine
        self.engine = sgtk.platform.start_engine("test_engine", self.tk, context)

        self.app = self.engine.apps["test_app"]
        self.framework = self.app.frameworks['tk-framework-desktopserver']
        self.framework_module = self.framework.import_module("tk_framework_desktopserver")
        self.mock_host = MockHost()
        self.wss_key = "12345"
        self.api = self.framework_module.get_shotgun_api(
            protocol_version=2,
            host=self.mock_host,
            wss_key=self.wss_key,
            process_manager=None,
        )
        self.config_root = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "fixtures",
                "config"
            )
        )

    def tearDown(self):
        """
        Fixtures teardown
        """
        # engine is held as global, so must be destroyed.
        cur_engine = sgtk.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()

        # important to call base class so it can clean up memory
        super(TestDesktopServerFramework, self).tearDown()












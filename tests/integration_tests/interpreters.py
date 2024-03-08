# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function

import os
import sys
import json
import platform
import tempfile

import unittest

from sgtk_integration_test import SgtkIntegrationTest
import sgtk
from sgtk.descriptor import create_descriptor, Descriptor
from sgtk.util.shotgun_path import ShotgunPath
import sgtk.util
import tk_toolchain.authentication

logger = sgtk.LogManager.get_logger(__name__)


@unittest.skipIf(
    os.environ.get("CI")
    and sys.version_info.major == 2
    and platform.system() == "Windows",
    "Skipping On Windows/Python2 because of error in authentication that needs to be investigated",
)
@unittest.skipIf(
    os.environ.get("CI") and platform.system() == "Linux",
    "Skipping On Linux because of a core dump that needs to be investigated",
)
class Python3ProjectTests(SgtkIntegrationTest):
    @classmethod
    def get_python_interpreter_by_major_version(cls, major):
        """
        Get the path to a python interpreter on the current platform that
        matches the given major version.
        """
        version = platform.python_version()

        # windows paths
        win_paths = {
            2: [r"C:\Program Files\Shotgun\Python\python.exe"],
            3: [r"C:\Program Files\Shotgun\Python3\python.exe"],
        }

        win_paths[int(version[0])].append(
            r"C:\hostedtoolcache\windows\Python\%s\x64\python.exe" % version
        )

        # linux paths
        linux_paths = {
            2: ["/opt/Shotgun/Python/bin/python"],
            3: ["/opt/Shotgun/Python3/bin/python"],
        }

        linux_paths[int(version[0])].append(
            r"/opt/hostedtoolcache/Python/%s/x64/bin/python" % version
        )

        # mac paths
        osx_paths = {
            2: ["/Applications/Shotgun.app/Contents/Resources/Python/bin/python"],
            3: ["/Applications/Shotgun.app/Contents/Resources/Python3/bin/python"],
        }

        osx_paths[int(version[0])].append(
            r"/Users/runner/hostedtoolcache/Python/%s/x64/bin/python" % version
        )

        paths = {
            "Windows": win_paths,
            "Linux": linux_paths,
            "Darwin": osx_paths,
        }

        for path in paths[platform.system()][major]:
            if os.path.exists(path):
                return path

        raise Exception(
            "Could not find a python version {} executable for {}".format(
                major, platform.system()
            )
        )

    @classmethod
    def write_interpreter_config_for_py_version(cls, major_version, cfg_path):
        """
        Write the path to the python interpreter matching a given version into the cfg_path file
        """
        path = cls.get_python_interpreter_by_major_version(major_version)
        with open(cfg_path, "w") as f:
            f.write(path)

    @classmethod
    def create_pipeline_config_for_python_version(
        cls, config_name, python_major_version
    ):
        """
        Copy the pipeline configuration from the fixtures folder and add the interpreter_*.cfg file that usese
        the specified version of python. Then create or update a pipeline configuration in Shotgun with the
        given name that points to the new pipeline config on disk
        """
        # Copy the fixture config into a temp location
        temp_folder = tempfile.mkdtemp()
        config_source_path = os.path.abspath(
            os.path.join(cls.fixtures_root, "config", "interpreter_test")
        )
        sgtk.util.filesystem.copy_folder(
            config_source_path,
            temp_folder,
        )

        # Find the correct interpreter and update the interpreter config file in the temp config
        cfg_descriptor = create_descriptor(
            None,
            Descriptor.CONFIG,
            dict(path=temp_folder, type="path"),
        )

        # Get the location of the interpreter file
        interpreter_config_filename = ShotgunPath.get_file_name_from_template(
            "interpreter_%s.cfg", sys.platform
        )
        interpreter_cfg_path = os.path.join(
            cfg_descriptor.get_path(), "core", interpreter_config_filename
        )

        # Write to the interpreter file
        cls.write_interpreter_config_for_py_version(
            python_major_version, interpreter_cfg_path
        )

        # Create or update the pipeline configuration in PTR to point to the temp config folder
        config_descriptor_str = "sgtk:descriptor:path?path=%s" % temp_folder
        pipeline_configuration = cls.create_or_update_pipeline_configuration(
            config_name,
            {
                "plugin_ids": "basic.*",
                "descriptor": config_descriptor_str,
                "project": cls.project,
            },
        )

        return pipeline_configuration

    @classmethod
    def setUpClass(cls):
        super(Python3ProjectTests, cls).setUpClass()

        cls.fixtures_root = os.path.join(
            os.path.dirname(__file__), "..", "..", "tests", "fixtures"
        )
        cls.bundles_root = os.path.join(cls.fixtures_root, "config", "bundles")
        os.environ["BUNDLES_ROOT"] = cls.bundles_root

        # Create a user and connection to Shotgun.
        sa = sgtk.authentication.ShotgunAuthenticator()
        cls.user = tk_toolchain.authentication._get_toolkit_user(sa, os.environ)
        cls.sg = cls.user.create_sg_connection()
        sgtk.set_authenticated_user(cls.user)

        cls.project = cls.create_or_update_project("Python Interpreter Test Project")

        # Create a config for python2 and one for python3
        if sys.version_info.major == 2:
            cls.python_config = cls.create_pipeline_config_for_python_version(
                "python2", 2
            )
        if sys.version_info.major == 3:
            cls.python_config = cls.create_pipeline_config_for_python_version(
                "python3", 3
            )

        # Bootstrap the test_engine and use it to get the client and server frameworks
        manager = sgtk.bootstrap.ToolkitManager(cls.user)
        manager.plugin_id = "basic.test"
        manager.pipeline_configuration = cls.python_config["id"]

        cls.engine = manager.bootstrap_engine("test_engine", cls.project)

        cls.sg_user = cls.engine.shotgun.find_one(
            "HumanUser", [["login", "is", cls.user.login]], []
        )

        cls.test_app_name = "test_app"
        app = cls.engine.apps[cls.test_app_name]
        cls.tk_fw_desktopserver = app.frameworks["tk-framework-desktopserver"]
        cls.tk_fw_dekstopclient = app.frameworks["tk-framework-desktopclient"]

        # Launch the server
        cls.tk_fw_desktopserver.launch_desktop_server(
            "https://shotgunlocalhost.com", cls.sg_user["id"]
        )

        # Launch the client
        create_client_module = cls.tk_fw_dekstopclient.import_module("create_client")
        cls.client = create_client_module.CreateClient(port_override=9000)

    @classmethod
    def tearDownClass(cls):
        cls.tk_fw_desktopserver.destroy_framework()

    def _test_execute_action(self, pipeline_config, command_name):
        """
        Execute a specific command on a pipeline configuration and make sure the command
        works as expected and writes its name into the file specified by the environment variable
        """
        data = {
            "pc": pipeline_config,
            "name": command_name,
            "entity_type": "Project",
            "entity_id": self.project["id"],
            "project_id": self.project["id"],
        }

        # Set the env var that the app uses as the file path to write the action name in
        test_file_path = os.path.join(self.temp_dir, "execute_action_test")
        os.environ["TK_FW_DESKTOP_SERVER_TEST_FILE_PATH"] = test_file_path

        # Call the action to write the file
        json.loads(self.client._call_server_method("execute_action", data))

        # Make sure the action was successful
        assert os.path.exists(test_file_path)
        with open(test_file_path, "r") as f:
            content = f.read()
        assert content == command_name

    @unittest.skipIf(
        sys.version_info.major == 3,
        "Skipping if major version of python is 3",
    )
    def test_execute_action_python2(self):
        """
        Make sure that calling "execute_action" of a python2 project works
        """
        self._test_execute_action(self.python_config, "Command A")

    @unittest.skipIf(
        sys.version_info.major == 2,
        "Skipping if major version of python is 2",
    )
    def test_execute_action_python3(self):
        """
        Make sure that calling "execute_action" of a python3 project works
        """
        self._test_execute_action(self.python_config, "Command B")

    def test_get_actions(self):
        """
        Make sure that calling "get_actions" works on both python2 and python3 projects
        """
        data = {
            "entity_type": "Project",
            "entity_id": self.project["id"],
            "project_id": self.project["id"],
        }

        reply = json.loads(self.client._call_server_method("get_actions", data))[
            "reply"
        ]
        assert "actions" in reply

        # The reply will hold actions from all pipeline configurations that apply to this project
        # If the sandbox is not clean, we will get more actions that we have set up in these configs
        # So we need to filter out the extras and just test that we get our expected result back from
        # the test configs
        test_config_ids = [self.python_config["id"]]
        test_data = set()
        for pc_name, pc_data in reply["actions"].items():
            if pc_data["config"]["id"] in test_config_ids:
                test_data = test_data.union(
                    {(pc_name, x["app_name"], x["title"]) for x in pc_data["actions"]}
                )
        if sys.version_info.major == 2:
            assert test_data == {
                ("python2", self.test_app_name, "Command A"),
                ("python2", self.test_app_name, "Command B"),
            }
        else:
            assert test_data == {
                ("python3", self.test_app_name, "Command A"),
                ("python3", self.test_app_name, "Command B"),
            }


if __name__ == "__main__":
    ret_val = unittest.main(failfast=True, verbosity=2)

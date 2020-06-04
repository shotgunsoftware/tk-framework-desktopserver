from __future__ import print_function

import os
import re
import json
import subprocess
import tempfile

import unittest2
from integration_test import DesktopServerIntegrationTest
import sgtk
from sgtk.descriptor import create_descriptor, Descriptor
from tank_vendor.shotgun_api3.lib import sgsix

logger = sgtk.LogManager.get_logger(__name__)


class Python3ProjectTests(DesktopServerIntegrationTest):

    @classmethod
    def get_python_executables(cls):
        """
        Find python interpreters and store them in a list along with their versions
        """
        aliases = ["python", "python2", "python3"]
        interpreter_paths = []
        interpreters = []
        if sgsix.platform == "win32":
            return interpreters
        else:
            # For Linux and Darwin use the 'which' command to discover possible python interpreter locations
            for alias in aliases:
                p = subprocess.Popen(["which", alias], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                out, err = p.communicate()
                if out:
                    out = out.rstrip("\n\r")
                    if os.path.exists(out):
                        interpreter_paths.append(out)

        for interp_path in interpreter_paths:

            # Get the version number for the interpreters
            p = subprocess.Popen([interp_path, "--version"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            out, err = p.communicate()
            pattern = re.compile("^Python (\d+)\.(\d+)\.(\d+)")
            m = pattern.match(out)

            # Some python versions write the output of --version to stderr
            if not m:
                m = pattern.match(err)

            if m:
                interpreters.append({
                    "major": int(m.group(1)),
                    "minor": int(m.group(2)),
                    "patch": int(m.group(3)),
                    "path": interp_path,
                })
        return interpreters

    @classmethod
    def get_python_interpreter_by_major_version(cls, major):
        """
        Get the path to a python interpreter that matches the given major version
        """
        for interp in cls.get_python_executables():
            if interp["major"] == major:
                return interp["path"]

    @classmethod
    def write_interpreter_config_for_py_version(cls, major_version, cfg_path):
        """
        Write the path to the python interpreter matching a given version into the cfg_path file
        """
        path = cls.get_python_interpreter_by_major_version(major_version)
        if not path:
            raise Exception("Couldn't find a python interpreter with major version %s" % major_version)
        with open(cfg_path, "w") as f:
            f.write(path)

    @classmethod
    def create_pipeline_config_for_python_version(cls, config_name, python_major_version):
        """
        Copy the pipeline configuration from the fixtures folder and add the interpreter_*.cfg file that usese
        the specified version of python. Then create or update a pipeline configuration in Shotgun with the
        given name that points to the new pipeline config on disk
        """
        # Copy the fixture config into a temp location
        temp_folder = tempfile.mkdtemp()
        config_source_path = os.path.abspath(os.path.join(cls.fixtures_root, "config", "interpreter_test"))
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
        interpreter_cfg_path = cfg_descriptor._get_current_platform_interpreter_file_name(cfg_descriptor.get_path())
        cls.write_interpreter_config_for_py_version(python_major_version, interpreter_cfg_path)

        # Create or update the pipeline configuration in SG to point to the temp config folder
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

        cls.project = cls.create_or_update_project("Python Interpreter Test Project")

        # Create a config for python2 and one for python3
        cls.python2_config = cls.create_pipeline_config_for_python_version("python2", 2)
        cls.python3_config = cls.create_pipeline_config_for_python_version("python3", 3)

        # Bootstrap the test_engine and use it to get the client and server frameworks
        manager = sgtk.bootstrap.ToolkitManager(cls.user)
        manager.plugin_id = "basic.test"
        manager.pipeline_configuration = cls.python2_config["id"]
        engine = manager.bootstrap_engine("test_engine", cls.project)
        cls.sg_user = engine.shotgun.find_one("HumanUser", [["login", "is", cls.user.login]], [])
        cls.tk_fw_dekstopserver = engine.frameworks["tk-framework-desktopserver"]
        cls.tk_fw_dekstopclient = engine.frameworks["tk-framework-desktopclient"]

        # Launch the server
        def get_aliases(x):
            return ["shotgunlocalhost.com"]

        cls.tk_fw_dekstopserver._get_host_aliases = get_aliases
        cls.tk_fw_dekstopserver.launch_desktop_server("shotgunlocalhost.com", cls.sg_user["id"])

        # Launch the client
        create_client_module = cls.tk_fw_dekstopclient.import_module("create_client")
        cls.client = create_client_module.CreateClient(port_override=9000)

    @classmethod
    def tearDownClass(cls):
        cls.tk_fw_dekstopserver.destroy_framework()

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

    def test_execute_action_python2(self):
        """
        Make sure that calling "execute_action" of a python2 project works
        """
        self._test_execute_action(self.python2_config, "Command A")

    def test_execute_action_python3(self):
        """
        Make sure that calling "execute_action" of a python3 project works
        """
        self._test_execute_action(self.python3_config, "Command B")

    def test_get_actions(self):
        """
        Make sure that calling "get_actions" works on both python2 and python3 projects
        """
        data = {
            "entity_type": "Project",
            "entity_id": self.project["id"],
            "project_id": self.project["id"],
        }

        reply = json.loads(self.client._call_server_method("get_actions", data))["reply"]
        assert "actions" in reply

        test_data = set()
        for pc in reply["actions"]:
            test_data = test_data.union({(pc, x["app_name"], x["title"]) for x in reply["actions"][pc]["actions"]})
        assert test_data == {
            ("python2", "test_app", "Command A"),
            ("python2", "test_app", "Command B"),
            ("python3", "test_app", "Command A"),
            ("python3", "test_app", "Command B"),
        }

if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
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
import glob
from command import Command

try:
    from sgtk.platform.qt import PySide
except:
    pass

from PySide import QtGui
from sgtk_file_dialog import SgtkFileDialog


class ProcessManager(object):
    """
    OS Interface for Shotgun Commands.
    """

    platform_name = "unknown"

    def _get_toolkit_script_name(self):
        return "shotgun"

    def _get_toolkit_fallback_script_name(self):
        return "tank"

    def _get_launcher(self):
        """
        Get Launcher file name from environement.
        This provides an alternative way to launch applications and open files, instead of os-standard open.

        :returns: String Default Launcher filename. None if none was found,
        """
        return os.environ.get("SHOTGUN_PLUGIN_LAUNCHER")

    def _verify_file_open(self, filepath):
        """
        Verify that a file can be opened.

        :param filepath: String file path that should be opened.
        :raises: Exception If filepath cannot be opened.
        """

        if not os.path.isfile(filepath):
            raise Exception("Error opening file [%s]. File not found." % filepath)

    def _get_full_toolkit_path(self, pipeline_config_path):
        """
        Get the full path of the toolkit script.

        :param pipeline_config_path: String Pipeline folder
        :return: String File path of toolkit script (eg: c:/temp/tank)
        """
        exec_script = os.path.join(pipeline_config_path, self._get_toolkit_script_name())

        if not os.path.isfile(exec_script):
            exec_script = os.path.join(pipeline_config_path, self._get_toolkit_fallback_script_name())

        return exec_script

    def _verify_toolkit_arguments(self, pipeline_config_path, command):
        """
        Verify that the arguments provided to the toolkit command are valid.

        :param pipeline_config_path: String Pipeline configuration path
        :param command: Toolkit command to run
        :raises: Exception On invalid toolkit command arguments.
        """

        if not command.startswith("shotgun"):
            raise Exception("ExecuteTankCommand error. Command needs to be a shotgun command [{command}]".format(command=command))

        if not os.path.isdir(pipeline_config_path):
            raise Exception("Could not find the Pipeline Configuration on disk: " + pipeline_config_path)

        exec_script = self._get_full_toolkit_path(pipeline_config_path)
        if not os.path.isfile(exec_script):
            raise Exception("Could not find the Toolkit command on disk: " + exec_script)

    def _launch_process(self, args, message_error="Error executing command."):
        """
        Standard way of starting a process and handling errors.

        :params args: List of elements to pass Popen.
        :params message_error: String to prefix error message in case of an error.
        :returns: Bool If the operation was successful
        """
        return_code, out, err = Command.call_cmd(args)
        has_error = return_code != 0

        if has_error:
            raise Exception("{message_error}\nCommand: {command}\nReturn code: {return_code}\nOutput: {std_out}\nError: {std_err}"
                            .format(message_error=message_error, command=args, return_code=return_code, std_out=out, std_err=err))

        return True

    def open(self, filepath):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        :return: Bool If the operation was successful
        """
        raise NotImplementedError("Open not implemented in base class!")

    def execute_toolkit_command(self, pipeline_config_path, command, args):
        """
        Execute Toolkit Command

        :param pipeline_config_path: String Pipeline configuration path
        :param command: Commands
        :param args: List Script arguments
        :returns: (stdout, stderr, returncode) Returns standard process output
        """

        try:
            self._verify_toolkit_arguments(pipeline_config_path, command)

            #
            # Get toolkit Script Path
            exec_script = self._get_full_toolkit_path(pipeline_config_path)

            # Get toolkit script argument list
            script_args = [command] + args

            #
            # Launch script
            exec_command = [exec_script] + script_args
            return_code, out, err = Command.call_cmd(exec_command)

            return (out, err, return_code)
        except Exception, e:
            raise Exception("Error executing toolkit command: " + e.message)

    def _add_action_output(self, actions, out, err, code):
        """
        Simple shortcut to quickly add process output to a dictionary
        """
        actions['out'] = out
        actions['err'] = err
        actions['retcode'] = code

    def get_project_actions(self, pipeline_config_paths):
        """
        Get all actions for all environments from project path

        :param pipeline_config_paths: [String] Pipeline configuration paths
        """

        project_actions = {}
        for pipeline_config_path in pipeline_config_paths:
            env_path = os.path.join(pipeline_config_path, "config", "env")
            env_glob = os.path.join(env_path, "shotgun_*.yml")
            env_files = glob.glob(env_glob)

            project_actions[pipeline_config_path] = {}

            for env_filepath in env_files:
                env_filename = os.path.basename(env_filepath)
                entity = os.path.splitext(env_filename.replace("shotgun_", ""))[0]
                cache_filename = "shotgun_" + self.platform_name + "_" + entity + ".txt"

                # Need to store where actions have occurred in order to give proper error message to client
                # This could be made much better in the future by creating the actual final actions from here instead.
                project_actions[pipeline_config_path][env_filename] = {"get": {}, "cache": {}}

                (out, err, code) = self.execute_toolkit_command(pipeline_config_path,
                                                                "shotgun_get_actions",
                                                                [cache_filename, env_filename])
                self._add_action_output(project_actions[pipeline_config_path][env_filename]['get'], out, err, code)

                if code == 1:
                    (out, err, code) = self.execute_toolkit_command(pipeline_config_path,
                                                                    "shotgun_cache_actions",
                                                                    [entity, cache_filename])
                    self._add_action_output(project_actions[pipeline_config_path][env_filename]['cache'], out, err, code)

                    if code == 0:
                        (out, err, code) = self.execute_toolkit_command(pipeline_config_path,
                                                                        "shotgun_get_actions",
                                                                        [cache_filename, env_filename])
                        self._add_action_output(project_actions[pipeline_config_path][env_filename]['get'], out, err, code)

        return project_actions


    def pick_file_or_directory(self, multi=False):
        """
        Pop-up a file selection window.

        Note: Currently haven't been able to get the proper native dialog to multi select
              both file and directories. Using this work-around for now.

        :param multi: Boolean Allow selecting multiple elements.
        :returns: List of files that were selected with file browser.
        """

        # If running outside of desktop, create a Qt App.
        if not QtGui.QApplication.instance():
            app = QtGui.QApplication([])

        dialog = SgtkFileDialog(multi, None)
        dialog.setResolveSymlinks(False)

        # Get result.
        result = dialog.exec_()

        files = []
        if result:
            files = dialog.selectedFiles()

            for f in files:
                if os.path.isdir(f):
                    f += os.path.sep

        return files

    @staticmethod
    def create():
        """
        Create Process Manager according to current context (such as os, etc..)

        :returns: ProcessManager
        """

        if sys.platform == "darwin":
            from process_manager_mac import ProcessManagerMac

            return ProcessManagerMac()
        elif os.name == "win32":
            from process_manager_win import ProcessManagerWin
            return ProcessManagerWin()
        elif sys.platform.startswith("linux"):
            from process_manager_linux import ProcessManagerLinux
            return ProcessManagerLinux()

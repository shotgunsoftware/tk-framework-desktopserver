# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Provides a base class for integration tests.
"""

from __future__ import print_function

import os
import tempfile
import atexit
from mock import Mock

import unittest2

import sgtk
from sgtk.util import sgre as re
from sgtk.util.filesystem import safe_delete_folder
import tk_toolchain.authentication


class DesktopServerIntegrationTest(unittest2.TestCase):
    """
    Base class for integration tests. Each integration test should be invoke in its own subprocess.

    The base class takes care of:
        - setting up a log file named after the test
        - creating a random temporary folder to write to or use the path pointed by SHOTGUN_TEST_TEMP
        - setting SHOTGUN_HOME to point to <temp_dir>/shotgun_home
        - authenticating a user using tk-toolchain
        - cleaning up the test folder when the tests are done running.
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """

        # Set up logging
        sgtk.LogManager().initialize_base_file_handler(
            cls._camel_to_snake(cls.__name__)
        )
        sgtk.LogManager().initialize_custom_handler()

        # Create a temporary directory for these tests and make sure
        # it is cleaned up.
        if "SHOTGUN_TEST_TEMP" not in os.environ:
            cls.temp_dir = tempfile.mkdtemp()
            # Only clean up the temp dir when not retrieving coverage for the tests,
            # or we won't be able ot merge the reports from all runs.
            if "SHOTGUN_TEST_COVERAGE" not in os.environ:
                # Do not rely on tearDown to cleanup files on disk. Use the atexit callback which is
                # much more reliable.
                atexit.register(cls._cleanup_temp_dir)
        else:
            cls.temp_dir = os.environ["SHOTGUN_TEST_TEMP"]

        # Ensures calls to the tempfile module generate paths under the unit test temp folder.
        tempfile.tempdir = cls.temp_dir

        # Ensure Toolkit writes to the temporary directory
        os.environ["SHOTGUN_HOME"] = os.path.join(cls.temp_dir, "shotgun_home")

        # Create a user and connection to Shotgun.
        sa = sgtk.authentication.ShotgunAuthenticator()
        cls.user = tk_toolchain.authentication._get_toolkit_user(sa, os.environ)
        cls.sg = cls.user.create_sg_connection()

        # Set the current user in memory for the server and in the file system for the script that
        # runs the actions in a separate process
        sgtk.set_authenticated_user(cls.user)
        sgtk.authentication.session_cache.set_current_host(cls.user.host)
        sgtk.authentication.session_cache.set_current_user(cls.user.host, cls.user.login)

        cls.fixtures_root = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures")
        cls.bundles_root = os.path.join(cls.fixtures_root, "config", "bundles")
        os.environ["BUNDLES_ROOT"] = cls.bundles_root

        # Mock Qt since we don't have it.
        sgtk.platform.qt.QtCore = Mock()
        sgtk.platform.qt.QtGui = Mock()

    @staticmethod
    def _camel_to_snake(text):
        """
        Converts a string from CamelCase to snake_case.
        """
        str1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", str1).lower()

    @classmethod
    def _cleanup_temp_dir(cls):
        """
        Called to cleanup the test folder.
        """
        # Close the file logger so that the file is not in use on Windows.
        sgtk.LogManager().uninitialize_base_file_handler()
        safe_delete_folder(cls.temp_dir)


    @classmethod
    def _create_unique_name(cls, name):
        """
        Returns a name that can be unique for the environment the test is running in.
        If SHOTGUN_TEST_ENTITY_SUFFIX environment variable is set, the suffix will be added.
        """
        if "SHOTGUN_TEST_ENTITY_SUFFIX" in os.environ:
            return "%s - %s" % (name, os.environ["SHOTGUN_TEST_ENTITY_SUFFIX"])
        else:
            return name

    @classmethod
    def create_or_update_project(cls, name, entity=None):
        """
        Creates or finds a project with a given name.

        :param str name: Name of the project to find or create.
        :param dict entity: Entity dictionary for the project if it needs to be created.

        .. note:
            The actual name of the project will be different than the name passed in. As such,
            always use the name returned from the entity.

        :returns: Entity dictionary of the project.
        """
        # Ensures only the requested fields are set so we don't confuse the roots
        # configuration detection.
        complete_project_data = {"tank_name": None}
        complete_project_data.update(entity or {})
        name = cls._create_unique_name("tk-framework-dekstopserver CI - %s" % name)
        return cls.create_or_update_entity("Project", name, complete_project_data)

    @classmethod
    def create_or_update_entity(cls, entity_type, name, entity_fields=None):
        """
        Creates of finds an entity with a given name

        :param str name: Name of the project to find or create.
        :param dict entity: Entity dictionary for the project if it needs to be created.

        .. note:
            The actual name of the entity might be different than the name passed in if you
            are in a CI environment. As such, always use the name returned from the entity.

        :returns: Entity dictionary of the project.
        """
        entity_fields = entity_fields or {}

        entity_name_field = sgtk.util.get_sg_entity_name_field(entity_type)

        filters = [[entity_name_field, "is", name]]

        # Filter by project, as not doing so can mean retrieving an asset with the
        # same name from another project.
        if "project" in entity_fields:
            filters.append(["project", "is", entity_fields["project"]])

        # Find the entity by this name in Shotgun for the specified project, if any.
        entity = cls.sg.find_one(entity_type, filters)
        # If it doesn't exist, create it!
        if not entity:
            entity_fields[entity_name_field] = name
            entity = cls.sg.create(entity_type, entity_fields)
        else:
            # But if it does, make sure it has the right data on it.
            cls.sg.update(entity_type, entity["id"], entity_fields)

        return entity

    @classmethod
    def create_or_update_pipeline_configuration(cls, name, entity_data):
        """
        Ensures a pipeline configuration with the given name exists.

        :param name: Name of the configuration to look for.
        :param entity_data: Data for the pipeline configuration that will be
            created or updated.
        """

        # Ensures only the requested fields are set so we don't confuse the bootstrap
        # process
        complete_pc_data = {
            "mac_path": "",
            "windows_path": "",
            "linux_path": "",
            "descriptor": "",
            "plugin_ids": "",
            # Turn on the associated feature pref if this field is giving out errors.
            "uploaded_config": None,
            "project": None,
        }
        complete_pc_data.update(entity_data)

        return cls.create_or_update_entity("PipelineConfiguration", name, entity_data)

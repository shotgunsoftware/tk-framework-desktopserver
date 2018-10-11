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

from tank_test.tank_test_base import setUpModule # noqa

from base_test import TestDesktopServerFramework, MockConfigDescriptor


class TestUtilMethods(TestDesktopServerFramework):
    """
    Tests for various utility methods for api_v2.
    """
    def test_payload_parsing(self):
        """
        Tests to ensure that payload parsing to extract entities passed down from
        Shotgun works properly.
        """
        project_entity = dict(
            type="Project",
            id=1,
        )

        shot_entities = [
            dict(
                type="Shot",
                id=2,
                project=project_entity,
            ),
            dict(
                type="Shot",
                id=3,
                project=project_entity,
            ),
            dict(
                type="Shot",
                id=4,
                project=project_entity,
            ),
        ]

        self.add_to_sg_mock_db([project_entity] + shot_entities)

        # If a single entity is passed down.
        test_payload = dict(
            project_id=1,
            entity_type="Shot",
            entity_id=2,
        )

        actual_return = self.api._get_entities_from_payload(test_payload)

        self.assertEqual(
            project_entity["id"],
            actual_return[0]["id"],
        )
        self.assertEqual(
            shot_entities[0]["id"],
            actual_return[1][0]["id"],
        )

        # If multiple entities are passed down.
        # If a single entity is passed down.
        test_payload = dict(
            project_id=1,
            entity_type="Shot",
            entity_ids=[2, 3, 4],
        )

        actual_return = self.api._get_entities_from_payload(test_payload)

        # Make sure we got the Project entity.
        self.assertEqual(
            project_entity["id"],
            actual_return[0]["id"],
        )

        # Make sure we can query the entity project if it isn't included.
        test_payload = dict(
            project_id=None,
            entity_type="Shot",
            entity_ids=[2, 3, 4],
        )

        # This will raise if it fails; no need to assert.
        self.api._get_entities_from_payload(test_payload)

        # The list of entities is unordered, so we can't just compare it directly.
        # Instead, we'll make sure the length is correct and that all of the expected
        # entities are there.
        self.assertEqual(len(shot_entities), len(actual_return[1]))

        for expected_entity in shot_entities:
            self.assertEqual(1, len([e for e in actual_return[1] if e["id"] == expected_entity["id"]]))

        # Check to make sure that we get a project entity back even if what's in
        # the payload is a None value for the project_id.
        task = dict(
            type="Task",
            id=9999,
            project=project_entity,
        )

        self.add_to_sg_mock_db([task])

        test_payload = dict(
            project_id=None,
            entity_type="Task",
            entity_id=9999,
        )

        actual_return = self.api._get_entities_from_payload(test_payload)
        self.assertEqual(project_entity["id"], actual_return[0]["id"])

        # Also check to see if the project_id is completely omitted from the payload.
        test_payload = dict(
            entity_type="Task",
            entity_id=9999,
        )

        actual_return = self.api._get_entities_from_payload(test_payload)
        self.assertTrue(isinstance(actual_return[0], dict))
        self.assertEqual(project_entity["id"], actual_return[0]["id"])

    def test_get_task_entity_parent_type(self):
        """
        Tests that we get the correct parent entity type from Tasks.
        """
        task_entities = [
            dict(
                type="Task",
                id=1,
                content="Linked to Shot",
                entity=dict(type="Shot", id=1),
            ),
            dict(
                type="Task",
                id=2,
                content="Linked to Asset",
                entity=dict(type="Asset", id=2),
            ),
        ]

        self.add_to_sg_mock_db(task_entities)
        self.assertEqual(self.api._get_task_parent_entity_type(task_id=1), "Shot")
        self.assertEqual(self.api._get_task_parent_entity_type(task_id=2), "Asset")

    def test_legacy_shotgun_environments(self):
        """
        Tests to ensure that a shotgun_xxx.yml file in a config includes
        that environment's "xxx" entity type in the whitelist of types supported
        by the RPC API.
        """
        config_descriptor = MockConfigDescriptor(
            path=self.config_root,
            is_immutable=False,
        )

        whitelist_1 = self.api._get_entity_type_whitelist(
            project_id=None,
            config_descriptor=config_descriptor,
        )

        # When the config is mutable, the shotgun_foobar.yml file in our config
        # fixture will result in a "foobar" entity type in the whitelist.
        self.assertTrue(("foobar" in whitelist_1))

        # We will also check to make sure that we get the same results when
        # the config is immutable.
        config_descriptor._is_immutable = True

        # We have to clear the entity cache, though, because the wss_key isn't
        # changing the way it would on a page refresh or navigation.
        self.api._cache = dict()

        whitelist_2 = self.api._get_entity_type_whitelist(
            project_id=None,
            config_descriptor=config_descriptor,
        )
        self.assertEqual(whitelist_1, whitelist_2)

    def test_get_software_entities(self):
        """
        Tests to ensure that we get a proper list of software entities from SG.
        """
        sw_entities = [
            {'code': '3ds Max', 'engine': 'tk-3dsmaxplus', 'id': 1, 'type': 'Software'},
            {'code': 'Houdini', 'engine': 'tk-houdini', 'id': 2, 'type': 'Software'},
            {'code': 'Maya', 'engine': 'tk-maya', 'id': 3, 'type': 'Software'},
            {'code': 'Nuke', 'engine': 'tk-nuke', 'id': 4, 'type': 'Software'},
            {'code': 'Photoshop', 'engine': 'tk-photoshopcc', 'id': 5, 'type': 'Software'},
            {'code': 'Flame', 'engine': 'tk-flame', 'id': 6, 'type': 'Software'}
        ]

        self.add_to_sg_mock_db(sw_entities)

        # Ensure that we get back the same number of entities as we put in.
        self.assertEqual(len(sw_entities), len(self.api._get_software_entities()))

        # Ensure that they were cached in memory.
        self.assertEqual(len(sw_entities), len(self.api._cache[self.api.SOFTWARE_ENTITIES]))

    def test_filter_by_project(self):
        """
        Tests to ensure that a list of input actions is filtered by project according
        Software entity settings.
        """
        sw = dict(
            code="Tester",
            engine="tk_engine_tester",
            id=7,
            type="Software",
            projects=[dict(type="Project", id=999), dict(type="Project", id=1000)],
        )
        self.add_to_sg_mock_db([sw])

        actions = [
            dict(
                title="This one passes",
                engine_name="tk-maya",
            ),
            dict(
                title="This one gets filtered out",
                engine_name="tk_engine_tester",
            ),
        ]

        project = dict(type="Project", id=1)
        filtered_actions = self.api._filter_by_project(
            actions,
            self.api._get_software_entities(),
            project,
        )

        # Make sure one got filtered out, and that the one remaining is
        # what's expected.
        self.assertEqual(len(filtered_actions), 1)
        self.assertEqual(filtered_actions[0], actions[0])

    def test_multiple_projects_per_software(self):
        """
        Tests to ensure that a software can be assigned to multiple projects.
        """
        sw_1 = dict(
            code="Tester",
            engine="tk_engine_tester",
            id=7,
            type="Software",
            projects=[dict(type="Project", id=999), dict(type="Project", id=1000)],
        )
        sw_2 = dict(
            code="Tester",
            engine="tk_engine_tester_2",
            id=8,
            type="Software",
            projects=[dict(type="Project", id=1000)],
        )
        self.add_to_sg_mock_db([sw_1, sw_2])

        actions = [
            dict(
                title="This should get returned for project 999 and 1000.",
                engine_name="tk_engine_tester",
            ),
            dict(
                title="This should get returned for project 1000.",
                engine_name="tk_engine_tester_2",
            )
        ]

        # filtered_actions = self.api._filter_by_project(
        #     actions,
        #     self.api._get_software_entities(),
        #     dict(type="Project", id=1),
        # )

        # Project 1 shouldn't match anything.
        # self.assertEqual(filtered_actions, [])

        filtered_actions = self.api._filter_by_project(
            actions,
            self.api._get_software_entities(),
            dict(type="Project", id=999),
        )

        # Project 999 can only use the action from tk_engine_tester.
        self.assertEqual(filtered_actions, [actions[0]])

        filtered_actions = self.api._filter_by_project(
            actions,
            self.api._get_software_entities(),
            dict(type="Project", id=1000),
        )

        # Project 1000 can only use the action from tk_engine_tester.
        self.assertEqual(filtered_actions, actions)

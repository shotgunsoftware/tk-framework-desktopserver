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

from tank_test.tank_test_base import setUpModule

# import the test base class
test_python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(test_python_path)
from base_test import TestDesktopServerFramework, MockConfigDescriptor

class TestCacheMethods(TestDesktopServerFramework):
    """
    Tests for various caching-related methods for api_v2.
    """
    def test_lookup_hash(self):
        """
        Tests to ensure that the lookup hash, which acts as the key for each
        row in the cache, is unique based on certain input data, and is stable
        across invokations.
        """
        config_descriptor = MockConfigDescriptor(
            path=self.config_root,
            is_immutable=True,
        )
        key_1 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=1),
            entity_type="Project",
            entity_id=1,
        )
        key_2 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=1),
            entity_type="Shot",
            entity_id=1,
        )

        # Different entity types should result in different keys.
        self.assertNotEqual(key_1, key_2)

        # Different entity id numbers should not make a difference with the
        # default browser_integration hook that we ship with. The exception
        # is Task entities, which are tested later in this method.
        key_3 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=1),
            entity_type="Shot",
            entity_id=11111,
        )
        self.assertEqual(key_2, key_3)

        # Different projects should not make a difference with the default
        # browser_integration hook that we ship with.
        key_4 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=11111),
            entity_type="Shot",
            entity_id=1,
        )
        self.assertEqual(key_3, key_4)

        # Task entities are treated special, because they can be linked to
        # different entity types (Shot and Asset, most likely). We key
        # the cache by Task AND the entity type it is linked to. This ensures
        # that Tasks linked to Shots can be configured to have different
        # actions than Tasks linked to Assets, as an example.
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

        key_5 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=11111),
            entity_type="Task",
            entity_id=1,
        )
        key_6 = self.api._get_lookup_hash(
            config_uri=config_descriptor.get_uri(),
            project=dict(type="Project", id=11111),
            entity_type="Task",
            entity_id=2,
        )

        # These should not match, because one Task entity is linked to a
        # Shot entity and the other to an Asset.
        self.assertNotEqual(key_5, key_6)

    def test_contents_hash(self):
        """
        Tests to ensure that the contents hash is properly constructed out of
        the component parts: a config descriptor, and the env yml file modtimes
        in the same where a mutable config is in use.
        """
        config_descriptor = MockConfigDescriptor(
            path=self.config_root,
            is_immutable=True,
        )
        hash_1 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )
        hash_2 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )

        # These should be the same since no input data changed.
        self.assertEqual(hash_1, hash_2)

        # Change the Software entities, which should cause the hash
        # to change.
        self.add_to_sg_mock_db([
            dict(
                code="Something New",
                engine="tk_engine_tester",
                id=8,
                type="Software",
                projects=[],
            )
        ])

        # We have to clear the entity cache, though, because the wss_key isn't
        # changing the way it would on a page refresh or navigation.
        self.api._cache = dict()
        hash_3 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )
        self.assertNotEqual(hash_1, hash_3)

        # Setting the descriptor to imply that the config is mutable should
        # also change the hash, as the mtimes of environment yml files will
        # be included in the hash.
        config_descriptor._is_immutable = False
        hash_4 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )
        self.assertNotEqual(hash_3, hash_4)

        # Running it again should match, because the mtimes of the yml files
        # have not changed.
        hash_5 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )
        self.assertEqual(hash_4, hash_5)

        # Updating mtimes should cause the hash to change again.
        os.utime(os.path.join(self.config_root, "env", "test.yml"), None)

        # We have to clear the entity cache, though, because the wss_key isn't
        # changing the way it would on a page refresh or navigation.
        self.api._cache = dict()
        hash_6 = self.api._get_contents_hash(
            config_descriptor,
            self.api._get_software_entities(),
        )
        self.assertNotEqual(hash_5, hash_6)
























# Copyright (c) 2017 Shotgun Software Inc.
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
import cPickle
import md5
import sqlite3
import json
import subprocess
import tempfile
import contextlib

import sgtk

###########################################################################
# Classes

class ShotgunAPI(object):
    """
    Public API
    Callable methods from client. Every one of these methods can be called from the client.
    """
    PUBLIC_API_METHODS = [
        "get_actions",
    ]
    SYNCHRONOUS_METHODS = [
        "get_actions",
    ]

    DATABASE_FORMAT_VERSION = 1

    SUCCESSFUL_LOOKUP = 0
    NO_ENVIRONMENT_FOR_ENTITY_TYPE = 2
    CACHING_ERROR = 3

    # BASE_CONFIG_URI = "sgtk:descriptor:app_store?name=tk-config-basic"
    BASE_CONFIG_URI = "sgtk:descriptor:dev?name=tk-config-basic&path=/Users/jeff/Documents/repositories/tk-config-basic"

    def __init__(self, host, process_manager):
        """
        API Constructor.
        Keep initialization pretty fast as it is created on every message.

        :param host: Host interface to communicate with. Abstracts the client.
        :param process_manager: Process Manager to use to interact with os processes.
        """
        self._host = host
        self._process_manager = process_manager
        self._engine = sgtk.platform.current_engine()

        # Cache path on disk.
        self._cache_path = os.path.join(
            self._engine.cache_location, 
            "shotgun_engine_commands_v%s.sqlite" % self.DATABASE_FORMAT_VERSION,
        )

    ###########################################################################
    # Properties

    @property
    def logger(self):
        return sgtk.platform.current_engine().logger

    @property
    def host(self):
        return self._host

    @property
    def process_manager(self):
        return self._process_manager

    ###########################################################################
    # Public methods

    def get_actions(self, data):
        # TODO: white listing is to be handled by core hook
        if data["entity_type"] not in ["Project", "Shot"]:
            self.host.reply(dict(retcode=self.NO_ENVIRONMENT_FOR_ENTITY_TYPE))
            return

        # If we weren't sent a usable entity id, we can just query the first one
        # from the project. This isn't a big deal for us, because we're only
        # concerned with picking the correct environment when we bootstrap
        # during a caching operation. This is going to be the situation when
        # a page is pre-loading entity-level commands on page load, as opposed to
        # passing down a specific entity that's been selected in an already-loaded
        # page.
        if data["entity_id"] == -1:
            temp_entity = self._engine.shotgun.find_one(
                data["entity_type"],
                [["project", "is", dict(type="Project", id=data["project_id"])]],
            )

            data["entity_id"] = temp_entity["id"]

        manager = sgtk.bootstrap.ToolkitManager()
        manager.base_configuration = self.BASE_CONFIG_URI
        project = dict(type="Project", id=data["project_id"])

        all_commands = dict()
        pcs = manager.get_pipeline_configurations(
            project,
            data["pipeline_configs"],
        ) or [dict(id=None, name="Primary")]

        # We'll need to pass up the config names in order along with a dict of
        # pc_name => commands.
        pc_names = [pc["name"] for pc in pcs]

        with self._db_connect() as (connection, cursor):
            for pc in pcs:
                # The hash that acts as the key we'll use to look up our cached
                # data will be based on the entity type and the pipeline config's
                # descriptor uri. We can get the descriptor from the toolkit
                # manager and pass that through along with the entity type from SG
                # to the core hook that computes the hash.
                manager.pipeline_configuration = pc["id"]
                pc_descriptor = manager.get_resolved_pipeline_configuration_descriptor(
                    data["project_id"],
                )

                lookup_hash = self._engine.sgtk.execute_core_hook_method(
                    "browser_integration",
                    "get_cache_lookup_hash",
                    entity_type=data["entity_type"],
                    pc_descriptor=pc_descriptor,
                )

                # TODO: Compute contents_hash and ensure it matches that in the cache.
                res = list(cursor.execute(
                    "SELECT commands FROM engine_commands WHERE lookup_hash=?",
                    (lookup_hash,)
                ))

                if res:
                    commands = cPickle.loads(str(list(res)[0][0]))
                    self.logger.debug("Commands found in cache: %s" % commands)
                    all_commands[pc["name"]] = commands
                else:
                    try:
                        self._cache_actions(data)
                    except subprocess.CalledProcessError, e:
                        self.logger.error(str(e))
                        self.host.reply(
                            dict(
                                err="Shotgun Desktop failed to get engine commands.",
                                retcode=self.CACHING_ERROR,
                                out="Caching failed!",
                            ),
                        )
                        return
                    else:
                        self.get_actions(data)
                        return

        self.host.reply(
            dict(
                err="",
                retcode=self.SUCCESSFUL_LOOKUP,
                commands=all_commands,
                pcs=pc_names,
            ),
        )

    ###########################################################################
    # Context managers

    @contextlib.contextmanager
    def _db_connect(self):
        connection = self._init_db()
        cursor = connection.cursor()
        yield (connection, cursor)
        cursor.close()
        connection.close()

    ###########################################################################
    # sqlite database access methods

    def _cache_actions(self, data):
        self.logger.info("Caching engine commands...")

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "cache_commands.py"
        )

        self.logger.debug("Executing script: %s" % script)
        args_file = tempfile.mkstemp()[1]

        with open(args_file, "w") as fh:
            cPickle.dump(
                dict(
                    cache_file=self._cache_path,
                    data=data,
                    sys_path=sys.path,
                ),
                fh,
                cPickle.HIGHEST_PROTOCOL,
            )

        output = None

        try:
            output = subprocess.check_output([sys.executable, script, args_file])
        except subprocess.CalledProcessError:
            if output:
                self.logger.error(output)
            raise
        else:
            self.logger.info(output)

        self.logger.info("Caching complete.")

    def _init_db(self):
        """
        Sets up the database if it doesn't exist.

        :returns: A handle that must be closed.
        """
        connection = sqlite3.connect(self._cache_path)

        # This is to handle unicode properly - make sure that sqlite returns 
        # str objects for TEXT fields rather than unicode. Note that any unicode
        # objects that are passed into the database will be automatically
        # converted to UTF-8 strs, so this text_factory guarantees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        connection.text_factory = str
        c = connection.cursor()

        try:
            # Get a list of tables in the current database.
            ret = c.execute("SELECT name FROM main.sqlite_master WHERE type='table';")
            table_names = [x[0] for x in ret.fetchall()]

            if not table_names:
                self.logger.debug("Creating schema in sqlite db.")

                # We have a brand new database. Create all tables and indices.
                c.executescript("""
                    CREATE TABLE engine_commands (lookup_hash text, contents_hash text, commands blob);
                """)
                # c.executescript("""
                #     -- CREATE TABLE entity (entity_type text, entity_id integer, activity_id integer, created_at datetime);

                #     -- CREATE TABLE activity (activity_id integer, note_id integer default null, payload blob, created_at datetime);

                #     -- CREATE TABLE note (note_id integer, payload blob, created_at datetime);

                #     -- CREATE INDEX entity_1 ON entity(entity_type, entity_id, created_at);
                #     -- CREATE INDEX entity_2 ON entity(entity_type, entity_id, activity_id, created_at);

                #     -- CREATE INDEX activity_1 ON activity(activity_id);
                #     -- CREATE INDEX activity_2 ON activity(activity_id, note_id);

                #     -- CREATE INDEX note_1 ON activity(note_id);
                # """)
                connection.commit()
        except Exception:
            connection.close()
            c = None
            raise
        finally:
            if c:
                c.close()

        return connection









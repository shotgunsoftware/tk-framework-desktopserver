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
import sqlite3
import json
import subprocess
import tempfile
import contextlib
import json
import fnmatch
import datetime

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

    # Return codes.
    SUCCESSFUL_LOOKUP = 0
    UNSUPPORTED_ENTITY_TYPE = 2
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
        """
        The associated engine's logger.
        """
        return self._engine.logger

    @property
    def host(self):
        """
        The host associated with the currnt RPC transaction.
        """
        return self._host

    @property
    def process_manager(self):
        """
        The process manager associated with this interface.
        """
        return self._process_manager

    ###########################################################################
    # Public methods

    def get_actions(self, data):
        """
        RPC method that sends back a dictionary containing engine commands
        for each pipeline configuration associated with the project.

        :param dict data: The data passed down by the client. At a minimum,
            the dict should contain the following keys: project_id, entity_id,
            entity_type, pipeline_configs, and user.
        """
        project_entity = dict(
            type="Project",
            id=data["project_id"],
        )
        entity = dict(
            type=data["entity_type"],
            id=data["entity_id"],
        )

        # We can end up getting requests for actions for any entity type
        # that exists in Shotgun. Many of those we don't want to provide
        # commands for, so we can just notify the client that it's an
        # unsupported entity type.
        env_name = self._engine.sgtk.execute_core_hook(
            sgtk.platform.constants.PICK_ENVIRONMENT_CORE_HOOK_NAME,
            context=sgtk.Context(
                self._engine.sgtk,
                project=project_entity,
                entity=entity,
            )
        )

        if env_name is None:
            self.host.reply(dict(retcode=self.UNSUPPORTED_ENTITY_TYPE))
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
                [["project", "is", project_entity]],
            )
            data["entity_id"] = temp_entity["id"]

        manager = sgtk.bootstrap.ToolkitManager()
        manager.base_configuration = self.BASE_CONFIG_URI

        pcs = manager.sort_and_filter_configuration_entities(
            project=project_entity,
            entities=data["pipeline_configs"],
        ) or [dict(id=None, name="Primary")]

        # We'll need to pass up the config names in order along with a dict of
        # pc_name => commands.
        pc_names = [pc["name"] for pc in pcs]
        all_commands = dict()
        config_data = dict()

        for pc in pcs:
            # The hash that acts as the key we'll use to look up our cached
            # data will be based on the entity type and the pipeline config's
            # descriptor uri. We can get the descriptor from the toolkit
            # manager and pass that through along with the entity type from SG
            # to the core hook that computes the hash.
            manager.pipeline_configuration = pc["id"]
            pc_descriptor = manager.resolve_descriptor(project_entity)
            pc_data = dict()
            pc_data["contents_hash"] = self._get_contents_hash(pc_descriptor)
            pc_data["lookup_hash"] = self._get_lookup_hash(pc_descriptor, data["entity_type"])
            pc_data["descriptor"] = pc_descriptor
            pc_data["entity"] = pc
            config_data[pc["id"]] = pc_data

        with self._db_connect() as (connection, cursor):
            for pc in pcs:
                # The hash that acts as the key we'll use to look up our cached
                # data will be based on the entity type and the pipeline config's
                # descriptor uri. We can get the descriptor from the toolkit
                # manager and pass that through along with the entity type from SG
                # to the core hook that computes the hash.
                pc_data = config_data[pc["id"]]
                manager.pipeline_configuration = pc["id"]
                pc_descriptor = pc_data["descriptor"]
                lookup_hash = pc_data["lookup_hash"]
                contents_hash = pc_data["contents_hash"]

                # TODO: Compute contents_hash and ensure it matches that in the cache.
                res = list(cursor.execute(
                    "SELECT commands, contents_hash FROM engine_commands WHERE lookup_hash=?",
                    (lookup_hash,)
                ))

                try:
                    if res:
                        # We'll only ever get back a single row, if anything.
                        cached_data = res[0]
                        cached_contents_hash = cached_data[1]

                        if str(contents_hash) == str(cached_contents_hash):
                            commands = self._engine.sgtk.execute_core_hook_method(
                                "browser_integration",
                                "process_commands",
                                commands=cPickle.loads(str(cached_data[0])),
                            )
                            self.logger.info("Commands found in cache: %s" % commands)
                            all_commands[pc["name"]] = commands
                        else:
                            self.logger.info("Cache is out of date, recaching: %s %s" % (contents_hash, cached_contents_hash))
                            self._cache_actions(data, config_data)
                            self.get_actions(data)
                            return
                    else:
                        self.logger.info("Commands not found in hash, caching now...")
                        self._cache_actions(data, config_data)
                        self.get_actions(data)
                        return
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
        """
        Context manager that initializes a DB connection on enter and
        disconnects on exit.
        """
        connection = self._init_db()
        cursor = connection.cursor()
        yield (connection, cursor)
        cursor.close()
        connection.close()

    ###########################################################################
    # sqlite database access methods

    def _cache_actions(self, data, config_data):
        """
        Triggers the caching or recaching of engine commands.

        :param dict data: The data passed down from the wss client.
        :param dict config_data: A dictionary keyed by PipelineConfiguration
            id containing a dict that contains, at a minimum, "lookup_hash"
            and "contents_hash" keys.
        """
        self.logger.info("Caching engine commands...")

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "cache_commands.py"
        )

        self.logger.debug("Executing script: %s" % script)
        args_file = tempfile.mkstemp()[1]
        hash_data = dict()

        for pc_id, pc_data in config_data.iteritems():
            hash_data[pc_id] = dict(
                lookup_hash=config_data[pc_id]["lookup_hash"],
                contents_hash = config_data[pc_id]["contents_hash"],
            )

        with open(args_file, "w") as fh:
            cPickle.dump(
                dict(
                    cache_file=self._cache_path,
                    data=data,
                    sys_path=sys.path,
                    base_configuration=self.BASE_CONFIG_URI,
                    hash_data=hash_data,
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

    def _get_contents_hash(self, config_descriptor):
        """
        Computes an md5 hashsum for the given pipeline configuration. This
        hash includes the state of all fields for all Software entities in
        the current Shotgun site, and if the given pipeline configuration
        is mutable, the modtimes of all yml files in the config.

        :param config_descriptor: The descriptor object for the pipeline config.

        :returns: hash value
        :rtype: int
        """
        sg = self._engine.shotgun

        # We're going to get all data associated with all Software entities
        # that exist.
        sw_entities = sg.find(
            "Software",
            [],
            fields=sg.schema_field_read("Software").keys(),
        )

        # We dump the entities out as json, sorting on keys to ensure 
        # consistent ordering of data.
        hashable_data = dict(
            entities=json.dumps(sw_entities, sort_keys=True, default=self.__json_default),
            modtimes="",
        )

        # If the config is mutable, we'll crawl its structure on disk, adding
        # the modtimes of all yml files found. When they're added to the digest,
        # we'll dump as json sorting alphanumeric on yml file name to ensure
        # consistent ordering of data.
        if config_descriptor.is_immutable() == False:
            yml_files = dict()

            for root, dir_names, file_names in os.walk(config_descriptor.get_path()):
                for file_name in fnmatch.filter(file_names, "*.yml"):
                    full_path = os.path.join(root, file_name)
                    yml_files[full_path] = os.path.getmtime(full_path)

            hashable_data["modtimes"] = json.dumps(yml_files, sort_keys=True)

        return hash(
            json.dumps(
                hashable_data,
                sort_keys=True,
            )
        )

    def _get_lookup_hash(self, config_descriptor, entity_type):
        """
        Computes a unique key for a row in a cache database for the given
        pipeline configuration descriptor and entity type.

        :param config_descriptor: A descriptor object for the pipeline configuration.
        :param str entity_type: The entity type.

        :returns: The computed lookup hash.
        :rtype: str
        """
        return "%s@%s" % (config_descriptor.get_uri(), entity_type)

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

    def __json_default(self, item):
        """
        Fallback logic for serialization of items that are not natively supported by the
        json library.

        :param item: The item to be serialized.

        :returns: A serialized equivalent of the given item.
        """
        if isinstance(item, datetime.datetime):
            return item.isoformat()
        raise TypeError("Item cannot be serialized: %s" % item)









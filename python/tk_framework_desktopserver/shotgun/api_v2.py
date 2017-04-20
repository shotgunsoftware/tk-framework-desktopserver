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
from sgtk.commands.clone_configuration import clone_pipeline_configuration_html
from sgtk.util import process

###########################################################################
# Classes

class ShotgunAPI(object):
    """
    Public API
    Callable methods from client. Every one of these methods can be called from the client.
    """
    PUBLIC_API_METHODS = [
        "get_actions",
        "execute_action",
    ]
    SYNCHRONOUS_METHODS = [
        "get_actions",
    ]

    # Stores data persistently per wss connection.
    WSS_KEY_CACHE = dict()

    DATABASE_FORMAT_VERSION = 1

    # Return codes.
    SUCCESSFUL_LOOKUP = 0
    UNSUPPORTED_ENTITY_TYPE = 2
    CACHING_ERROR = 3
    COMMAND_SUCCEEDED = 0
    COMMAND_FAILED = 1

    BASE_CONFIG_URI = os.environ.get(
        "SHOTGUN_DESKTOP_CONFIG_FALLBACK_DESCRIPTOR",
        "sgtk:descriptor:app_store?name=tk-config-basic"
    )
    ENGINE_NAME = "tk-shotgun"

    def __init__(self, host, process_manager, wss_key):
        """
        API Constructor.
        Keep initialization pretty fast as it is created on every message.

        :param host: Host interface to communicate with. Abstracts the client.
        :param process_manager: Process Manager to use to interact with os processes.
        :param str wss_key: The WSS connection's unique key.
        """
        self._host = host
        self._engine = sgtk.platform.current_engine()
        self._wss_key = wss_key

        if self._wss_key not in self.WSS_KEY_CACHE:
            self.WSS_KEY_CACHE[self._wss_key] = dict()

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

    ###########################################################################
    # Public methods

    def execute_action(self, data):
        """
        Executes the engine command associated with the action triggered
        in the client.

        :param dict data: The payload from the client.
        """
        if data["name"] == "__clone_pc":
            self.logger.debug("Clone configuration command received.")
            try:
                self._clone_configuration(data)
            except Exception as e:
                self.host.reply(
                    dict(
                        retcode=self.COMMAND_FAILED,
                        err=str(e),
                        out=str(e),
                    ),
                )
                raise
            else:
                self.logger.debug("Clone configuration successful.")
                self.host.reply(
                    dict(
                        retcode=self.COMMAND_SUCCEEDED,
                        err="",
                        out="",
                    ),
                )
                return

        project_entity, entities = self._get_entities_from_payload(data)

        # It shouldn't ever happen at this stage of the workflow, but we'll
        # check to make sure that we can get an environment for the type of
        # we're dealing with here.
        env_name = self.__pick_environment(project_entity, entities[0])

        if env_name is None:
            self.logger.error(
                "The provided entity does not correspond to any environment."
            )
            return

        args_file = self._get_arguments_file(
            dict(
                config=data["pc"],
                name=data["name"],
                entities=entities,
                project=project_entity,
                sys_path=sys.path,
                base_configuration=self.BASE_CONFIG_URI,
                engine_name=self.ENGINE_NAME,
            ),
        )

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "execute_command.py"
        )

        output = None

        # We'll need the Python executable when we shell out. We can't
        # rely on sys.executable, because that's going to be the Desktop
        # exe on Windows. We'll pull from the site config's interpreter
        # cfg file.
        python_exe = sgtk.get_python_interpreter_for_config(
            self._engine.sgtk.pipeline_configuration.get_path(),
        )
        self.logger.debug("Python executable: %s" % python_exe)

        try:
            kwargs = self._get_subprocess_kwargs()
            output = process.subprocess_check_output(
                [python_exe, script, args_file],
                **kwargs
            )
        except process.SubprocessCalledProcessError:
            if output:
                self.logger.error(output)
            # TODO: This needs to be reported to the client somehow.
            raise
        else:
            self.logger.debug(output)

        self.logger.debug("Command execution complete.")
        self.host.reply(
            dict(
                retcode=self.COMMAND_SUCCEEDED,
                out="Command executed successfully.",
                err="",
            ),
        )

    def get_actions(self, data):
        """
        RPC method that sends back a dictionary containing engine commands
        for each pipeline configuration associated with the project.

        :param dict data: The data passed down by the client. At a minimum,
            the dict should contain the following keys: project_id, entity_id,
            entity_type, pipeline_configs, and user.
        """
        # If we weren't sent a usable entity id, we can just query the first one
        # from the project. This isn't a big deal for us, because we're only
        # concerned with picking the correct environment when we bootstrap
        # during a caching operation. This is going to be the situation when
        # a page is pre-loading entity-level commands on page load, as opposed to
        # passing down a specific entity that's been selected in an already-loaded
        # page.
        if "entity_id" in data and data["entity_id"] == -1:
            if data["entity_type"] == "Project":
                data["entity_id"] = data["project_id"]
            else:
                temp_entity = self._engine.shotgun.find_one(
                    data["entity_type"],
                    [["project", "is", dict(type="Project", id=data["project_id"])]],
                )
                data["entity_id"] = temp_entity["id"]

        project_entity, entities = self._get_entities_from_payload(data)
        entity = entities[0]

        # We can end up getting requests for actions for any entity type
        # that exists in Shotgun. Many of those we don't want to provide
        # commands for, so we can just notify the client that it's an
        # unsupported entity type.
        env_name = self.__pick_environment(project_entity, entity)

        if env_name is None:
            self.host.reply(dict(retcode=self.UNSUPPORTED_ENTITY_TYPE))
            return

        manager = sgtk.bootstrap.ToolkitManager()
        manager.base_configuration = self.BASE_CONFIG_URI
        pcs = self._get_pipeline_configurations(
            manager,
            project_entity,
        ) or [dict(id=None, name="Primary")]

        # We'll need to pass up the config names in order along with a dict of
        # pc_name => commands.
        pc_names = [pc["name"] for pc in pcs]
        all_actions = dict()
        config_data = dict()

        for pc in pcs:
            # The hash that acts as the key we'll use to look up our cached
            # data will be based on the entity type and the pipeline config's
            # descriptor uri. We can get the descriptor from the toolkit
            # manager and pass that through along with the entity type from SG
            # to the core hook that computes the hash.
            manager.pipeline_configuration = pc["id"]
            pc_descriptor = manager.resolve_descriptor(project_entity)
            pc_key = pc_descriptor.get_uri()

            pc_data = dict()
            pc_data["contents_hash"] = self._get_contents_hash(
                pc_descriptor,
                self._get_site_state_data(),
            )
            pc_data["lookup_hash"] = self._get_lookup_hash(
                pc_key,
                project_entity,
                data["entity_type"],
            )
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

                cursor.execute(
                    "SELECT commands, contents_hash FROM engine_commands WHERE lookup_hash=?",
                    (lookup_hash,)
                )
                cached_data = list(cursor.fetchone() or [])

                try:
                    if cached_data:
                        cached_contents_hash = cached_data[1]

                        if str(contents_hash) == str(cached_contents_hash):
                            actions = self._process_commands(
                                commands=cPickle.loads(str(cached_data[0])),
                                project=project_entity,
                                entities=entities,
                            )
                            self.logger.debug("Actions found in cache: %s" % actions)
                            all_actions[pc["name"]] = dict(
                                actions=self._filter_by_project(
                                    actions,
                                    self._get_software_entities(),
                                    project_entity,
                                ),
                                config=pc,
                            )
                        else:
                            self.logger.debug(
                                "Cache is out of date, recaching: %s %s" % (
                                    contents_hash, cached_contents_hash
                                )
                            )
                            self._cache_actions(data, config_data)
                            self.get_actions(data)
                            return
                    else:
                        self.logger.debug("Commands not found in hash, caching now...")
                        self._cache_actions(data, config_data)
                        self.get_actions(data)
                        return
                except process.SubprocessCalledProcessError, e:
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
                actions=all_actions,
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

        with connection:
            with contextlib.closing(connection.cursor()) as cursor:
                yield (connection, cursor)

    ###########################################################################
    # Internal methods

    def _cache_actions(self, data, config_data):
        """
        Triggers the caching or recaching of engine commands.

        :param dict data: The data passed down from the wss client.
        :param dict config_data: A dictionary keyed by PipelineConfiguration
            id containing a dict that contains, at a minimum, "lookup_hash"
            and "contents_hash" keys.
        """
        self.logger.debug("Caching engine commands...")

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "cache_commands.py"
        )

        self.logger.debug("Executing script: %s" % script)
        hash_data = dict()

        # We'll need the Python executable when we shell out. We can't
        # rely on sys.executable, because that's going to be the Desktop
        # exe on Windows. We'll pull from the site config's interpreter
        # cfg file.
        python_exe = sgtk.get_python_interpreter_for_config(
            self._engine.sgtk.pipeline_configuration.get_path(),
        )
        self.logger.debug("Python executable: %s" % python_exe)

        for pc_id, pc_data in config_data.iteritems():
            hash_data[pc_id] = dict(
                lookup_hash=config_data[pc_id]["lookup_hash"],
                contents_hash=config_data[pc_id]["contents_hash"],
            )

        args_file = self._get_arguments_file(
            dict(
                cache_file=self._cache_path,
                data=data,
                sys_path=sys.path,
                base_configuration=self.BASE_CONFIG_URI,
                hash_data=hash_data,
                engine_name=self.ENGINE_NAME,
            )
        )

        output = None

        try:
            kwargs = self._get_subprocess_kwargs()
            output = process.subprocess_check_output(
                [python_exe, script, args_file],
                **kwargs
            )
        except process.SubprocessCalledProcessError:
            if output:
                self.logger.error(output)
            # This will bubble up to get_actions and be handled there.
            raise
        else:
            self.logger.debug(output)

        self.logger.debug("Caching complete.")

    def _clone_configuration(self, data):
        """
        Clones a pipeline configuration.

        :param dict data: The payload from the client. Requires the
            special "custom_data" key, which contains the relevant
            path data for the cloning operation.
        """
        # Custom data passed in entity_type:
        # USER_ID:NAME:LINUX_PATH:MAC_PATH:WINDOWS_PATH
        fields = data["custom_data"].split(":")
        user_id = int(fields[0])
        new_name = fields[1]
        new_path_linux = fields[2]
        new_path_mac = fields[3]

        # Note: Since the windows path may contain colons, assume all items
        # past the 4th chunk in the command is part of the windows path.
        new_path_windows = ":".join(fields[4:])
        pc_entity_id = data.get("entity_id") or data["entity_ids"][0]

        clone_pipeline_configuration_html(
            self.logger,
            self._engine.sgtk,
            pc_entity_id,
            user_id,
            new_name,
            new_path_linux,
            new_path_mac,
            new_path_windows,
            sgtk.pipelineconfig_utils.is_localized(data["pc_root_path"]),
        )

    def _filter_by_project(self, actions, sw_entities, project):
        """
        Filters out any actions that aren't permitted for the given project
        by the action's associated Software entity in Shotgun. The gist of how
        how all of this fits together is that we cache agnostic of any
        specific project. That being the case, once we've pulled the actions
        from the cache, we need to filter out any that are not permitted for
        use within the given project by the "projects" field's data from the
        associated Software entity in Shotgun.

        :param list actions: A list of action dictionaries, as stored in
            and queried from the api's associated sqlite database.
        :param list sw_entities: The list of Software entity dictionaries
            as queried from the Shotgun site.
        :param dict project: The project entity associated with the client
            request.

        :returns: A filtered list of actions. Those not permitted for use
            in the requesting project will have been removed.
        :rtype: list
        """
        filtered = []

        for action in actions:
            # We're only interested in entities that are referring to the
            # same engine as is recorded in the action dict.
            associated_sw = [s for s in sw_entities if s["engine"] == action.get("engine_name")]

            # Check the project against the projects list for matching Software
            # entities. If a Software entity's projects list is empty, then there
            # is no filtering to be done, as it's accepted by all projects.
            for sw in associated_sw:
                for sw_project in sw.get("projects", []):
                    if sw_project["id"] != project["id"]:
                        self.logger.debug("Action %s filtered due to SW entity projects." % action)
                        filtered.append(action)
                        break
                if action in filtered:
                    break

        return [a for a in actions if a not in filtered]

    def _get_arguments_file(self, args_data):
        """
        Dumps out a temporary file containing the provided data structure.

        :param args_data: The data to serialize to disk.

        :returns: File path
        :rtype: str
        """
        args_file = tempfile.mkstemp()[1]

        with open(args_file, "wb") as fh:
            cPickle.dump(
                args_data,
                fh,
                cPickle.HIGHEST_PROTOCOL,
            )

        return args_file

    def _get_contents_hash(self, config_descriptor, entities):
        """
        Computes an md5 hashsum for the given pipeline configuration. This
        hash includes the state of all fields for all Software entities in
        the current Shotgun site, and if the given pipeline configuration
        is mutable, the modtimes of all yml files in the config.

        :param config_descriptor: The descriptor object for the pipeline config.
        :param list entities: A list of entity dictionaries to be included in the
            hash computation.

        :returns: hash value
        :rtype: int
        """
        # We dump the entities out as json, sorting on keys to ensure 
        # consistent ordering of data.
        hashable_data = dict(
            entities=entities,
            modtimes="",
        )

        # If the config is mutable, we'll crawl its structure on disk, adding
        # the modtimes of all yml files found. When they're added to the digest,
        # we'll dump as json sorting alphanumeric on yml file name to ensure
        # consistent ordering of data.
        if config_descriptor and config_descriptor.is_immutable() == False:
            yml_files = dict()

            # TODO: Deeper traversal that takes into account possible includes stuff
            # based on environment variables, which this might not catch if the included
            # file is outside of the config. <jbee>
            for root, dir_names, file_names in os.walk(config_descriptor.get_path()):
                for file_name in fnmatch.filter(file_names, "*.yml"):
                    full_path = os.path.join(root, file_name)
                    yml_files[full_path] = os.path.getmtime(full_path)

            hashable_data["modtimes"] = yml_files

        return hash(
            json.dumps(
                hashable_data,
                sort_keys=True,
                default=self.__json_default,
            )
        )

    def _get_entities_from_payload(self, data):
        """
        Extracts the relevant entity information from the given payload data.

        :param dict data: The payload data.

        :returns: The project_entity, and a list of entities, in
            that order.
        :rtype: tuple
        """
        project_entity = dict(
            type="Project",
            id=data["project_id"],
        )

        if "entity_id" in data:
            entity = dict(
                type=data["entity_type"],
                id=data["entity_id"],
            )
            return (project_entity, [entity])
        elif "entity_ids" in data:
            entities = [dict(type=data["entity_type"], id=i) for i in data["entity_ids"]]
            return (project_entity, entities)
        else:
            raise RuntimeError("Unable to determine an entity from data: %s" % data)

    def _get_lookup_hash(self, config_uri, project, entity_type):
        """
        Computes a unique key for a row in a cache database for the given
        pipeline configuration descriptor and entity type.

        :param str config_uri: The pipeline configuration's descriptor uri.
        :param dict project: The project entity.
        :param str entity_type: The entity type.

        :returns: The computed lookup hash.
        :rtype: str
        """
        return self._engine.sgtk.execute_core_hook_method(
            "browser_integration",
            "get_cache_key",
            config_uri=config_uri,
            project=project,
            entity_type=entity_type
        )

    def _get_pipeline_configurations(self, manager, project):
        """
        Gets all PipelineConfiguration entities for the given project.

        :param bsm manager: The bootstrap toolkit manager object.
        :type pc: :class:`~sgtk.bootstrap.ToolkitManager`
        :param dict project: The project entity.

        :returns: A list of PipelineConfiguration entity dictionaries.
        :rtype: list
        """
        if "pipeline_configurations" not in self.WSS_KEY_CACHE[self._wss_key]:
            self.WSS_KEY_CACHE[self._wss_key]["pipeline_configurations"] = dict()

        pc_data = self.WSS_KEY_CACHE[self._wss_key]["pipeline_configurations"]

        if project["id"] not in pc_data:
            pc_data[project["id"]] = manager.get_pipeline_configurations(
                project=project,
            )
        else:
            self.logger.debug(
                "Cached PipelineConfiguration entities found for %s" % self._wss_key
            )

        return pc_data[project["id"]]

    def _get_site_state_data(self):
        """
        Gets state-related data for the site. Exactly what data this is depends
        on the "browser_integration" core hook's "get_site_state_data" method,
        which returns a list of dicts passed to the Shotgun Python API's find
        method as kwargs. The data returned by this method is cached based on
        the WSS connection key provided to the API's constructor at instantiation
        time. This means that this data is queried from Shotgun only once per
        unique WSS connection.

        :returns: A list of Shotgun entity dictionaries.
        :rtype: list
        """
        if "site_state_data" not in self.WSS_KEY_CACHE[self._wss_key]:
            self.WSS_KEY_CACHE[self._wss_key]["site_state_data"] = []

            requested_data_specs = self._engine.sgtk.execute_core_hook_method(
                "browser_integration",
                "get_site_state_data",
            )

            for spec in requested_data_specs:
                entities = self._engine.shotgun.find(**spec)
                self.WSS_KEY_CACHE[self._wss_key]["site_state_data"].extend(entities)
        else:
            self.logger.debug("Cached site state data found for %s" % self._wss_key)

        return self.WSS_KEY_CACHE[self._wss_key]["site_state_data"]

    def _get_software_entities(self):
        """
        Gets all Software entities from the Shotgun client site. Included are
        all existing fields. This data is cached per WSS connection key that
        was provided to the API's constructor at instantiation time. This means
        that this data is queried from SHotgun only once per unique WSS
        connection.

        :returns: A list of Software entity dictionaries.
        :rtype: list
        """
        if "software_entities" not in self.WSS_KEY_CACHE[self._wss_key]:
            self.WSS_KEY_CACHE[self._wss_key]["software_entities"] = self._engine.shotgun.find(
                "Software",
                [],
                fields=self._engine.shotgun.schema_field_read("Software").keys(),
            )
        else:
            self.logger.debug("Cache software entities found for %s" % self._wss_key)

        return self.WSS_KEY_CACHE[self._wss_key]["software_entities"]

    def _get_subprocess_kwargs(self):
        """
        Builds a list of kwargs to be passed to subprocesses.

        :returns: A dict of kwargs.
        :rtype: dict
        """
        kwargs = dict()

        # If we're on Windows, we'll want to stop the cmd.exe window
        # from flashing on/off when our subprocesses are run.
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = si

        return kwargs

    def _init_db(self):
        """
        Sets up the database if it doesn't exist. Calling this method directly
        is not advised. It's best to instead make use of the _db_connect
        context manager provided by this object.

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

        with contextlib.closing(connection.cursor()) as c:
            # Get a list of tables in the current database.
            ret = c.execute("SELECT name FROM main.sqlite_master WHERE type='table';")
            table_names = [x[0] for x in ret.fetchall()]

            if not table_names:
                self.logger.debug("Creating schema in sqlite db.")

                # We have a brand new database. Create all tables and indices.
                c.executescript("""
                    CREATE TABLE engine_commands (lookup_hash text, contents_hash text, commands blob);
                """)

                connection.commit()

        return connection

    def _process_commands(self, commands, project, entities):
        """
        Filters out commands that are not associated with an app, and then
        calls the process_commands methods from the browser_integration
        core hook, returning the result.

        :param list commands: The list of command dictionaries to be processed.
        :param dict project: The project entity.
        :param list entities: The list of entities that were passed down by the
            client.

        :returns: A list of commands dictionaries.
        :rtype: list
        """
        # Filter out any commands that didn't come from an app. This will
        # filter out things like the "Reload and Restart" command.
        filtered = list()

        for command in commands:
            if command["app_name"] is not None:
                filtered.append(command)
            else:
                self.logger.debug(
                    "Command filtered out for browser integration: %s" % command
                )

        return self._engine.sgtk.execute_core_hook_method(
            "browser_integration",
            "process_commands",
            commands=commands,
            project=project,
            entities=entities,
        )

    ###########################################################################
    # Private methods

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

    def __pick_environment(self, project_entity, entity):
        """
        Calls the pick_environment core hook on a context built from the
        provided entity.

        :param dict project_entity: The project entity dictionary.
        :param dict entity: The entity dictionary.

        :returns: The name of the associated environment, or None.
        :rtype: str or None
        """
        return self._engine.sgtk.execute_core_hook(
            sgtk.platform.constants.PICK_ENVIRONMENT_CORE_HOOK_NAME,
            context=sgtk.Context(
                self._engine.sgtk,
                project=project_entity,
                entity=entity,
            )
        )









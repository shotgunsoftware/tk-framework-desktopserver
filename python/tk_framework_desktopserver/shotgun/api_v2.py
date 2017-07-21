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
import re
import cPickle
import sqlite3
import json
import tempfile
import contextlib
import datetime
import copy
import base64
import glob
import threading
import hashlib

import sgtk
from sgtk import TankFileDoesNotExistError
from sgtk.commands.clone_configuration import clone_pipeline_configuration_html
from . import constants
from .. import command

logger = sgtk.platform.get_logger(__name__)

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
        "open",
        "pick_file_or_directory",
        "pick_files_or_directories",
    ]

    # Stores data persistently per wss connection.
    WSS_KEY_CACHE = dict()
    DATABASE_FORMAT_VERSION = 1
    SOFTWARE_FIELDS = ["id", "code", "updated_at", "type", "engine", "projects"]
    TOOLKIT_MANAGER = None

    # Keys for the in-memory cache.
    TASK_PARENT_TYPES = "task_parent_types"
    PIPELINE_CONFIGS = "pipeline_configurations"
    SITE_STATE_DATA = "site_state_data"
    CONFIG_DATA = "config_data"
    SOFTWARE_ENTITIES = "software_entities"
    ENTITY_TYPE_WHITELIST = "entity_type_whitelist"
    LEGACY_PROJECT_ACTIONS = "legacy_project_actions"
    YML_FILE_DATA = "yml_file_data"

    # We need to protect against concurrent bootstraps happening.
    # This is a reentrant lock because get_actions is recursive
    # when caching occurs, so might need to lock multiple times
    # within the same thread.
    _LOCK = threading.RLock()

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
        self._bundle = sgtk.platform.current_bundle()
        self._wss_key = wss_key
        self._logger = sgtk.platform.get_logger("api-v2")
        self._process_manager = process_manager

        if constants.DISABLE_LEGACY_BROWSER_INTEGRATION_WORKAROUND in os.environ:
            logger.debug("Legacy tank command pathway disabled.")
            self._allow_legacy_workaround = False
        else:
            logger.debug("Legacy tank command pathway allowed for classic configs.")
            self._allow_legacy_workaround = True

        if self._wss_key not in self.WSS_KEY_CACHE:
            self.WSS_KEY_CACHE[self._wss_key] = dict()

        self._cache = self.WSS_KEY_CACHE[self._wss_key]

        # Cache path on disk.
        self._cache_path = os.path.join(
            self._engine.cache_location,
            "shotgun_engine_commands_v%s.sqlite" % self.DATABASE_FORMAT_VERSION,
        )

    ###########################################################################
    # Properties

    @property
    def host(self):
        """
        The host associated with the currnt RPC transaction.
        """
        return self._host

    @property
    def process_manager(self):
        """
        The process manager object used to interact with os processes.
        """
        return self._process_manager

    ###########################################################################
    # Public methods

    @sgtk.LogManager.log_timing
    def execute_action(self, data):
        """
        Executes the engine command associated with the action triggered
        in the client.

        :param dict data: The payload from the client.
        """
        if data["name"] == "__clone_pc":
            logger.debug("Clone configuration command received.")
            try:
                self._clone_configuration(data)
            except Exception as e:
                self.host.reply(
                    dict(
                        retcode=constants.COMMAND_FAILED,
                        err=str(e),
                        out=str(e),
                    ),
                )
                raise
            else:
                logger.debug("Clone configuration successful.")
                self.host.reply(
                    dict(
                        retcode=constants.COMMAND_SUCCEEDED,
                        err="",
                        out="",
                    ),
                )
                return

        project_entity, entities = self._get_entities_from_payload(data)
        config_entity = data["pc"]
        command_name = data["name"]

        # We have to do a couple of things here. The first is that we ALWAYS
        # stick to the non-legacy code path for the __core_info and __upgrade_check
        # commands. Neither of these require a bootstrap to occur, and are therefore
        # fast when run through the modern code path. In addition, the implementation
        # of these "special" project-level commands already outputs markdown syntax,
        # which is preferable to the HTML we would get from the tank command.
        #
        # The second bit is that we can identify commands that need to be run in
        # legacy mode by whether the config entity dictionary we got from the client
        # contains a "_legacy_config_root" key that was shoved into it when the
        # get_actions method ran through its own legacy code path. In that case, we
        # shell out to the tank command by way of our process_manager object instead
        # of using the modern code path.
        if command_name not in constants.LEGACY_EXEMPT_ACTIONS and self._allow_legacy_workaround:
            if constants.LEGACY_CONFIG_ROOT in config_entity:
                # The arguments list is the name of the command, then the entity
                # type, and then a comma-separated list of entity ids.
                entity_ids = [str(e["id"]) for e in entities]
                (out, err, retcode) = self.process_manager.execute_toolkit_command(
                    config_entity[constants.LEGACY_CONFIG_ROOT],
                    "shotgun_run_action",
                    [data["name"], entities[0]["type"], ",".join(entity_ids)],
                )

                # Sanitize the output. By going the legacy route here, we're going
                # to end up with HTML in the output from the tank command. We need
                # to filter that and sanitize anything we keep, because the client
                # is going to believe that we're sending v2-style output, which is
                # taken and displayed as is, and is assumed to be markdown and not
                # HTML.
                self.host.reply(
                    dict(
                        retcode=retcode,
                        err=self._legacy_sanitize_output(err),
                        out=self._legacy_sanitize_output(out),
                    )
                )

                return

        args_file = self._get_arguments_file(
            dict(
                config=config_entity,
                name=data["name"],
                entities=entities,
                project=project_entity,
                sys_path=self._compute_sys_path(),
                base_configuration=constants.BASE_CONFIG_URI,
                engine_name=constants.ENGINE_NAME,
                logging_prefix=constants.LOGGING_PREFIX,
                bundle_cache_fallback_paths=self._engine.sgtk.bundle_cache_fallback_paths
            ),
        )

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "execute_command.py"
        )

        # We'll need the Python executable when we shell out. We need to make
        # sure it's what's in the config's interpreter config file. To do that,
        # we can get the config's descriptor object from the manager and ask
        # it for the path. By this point, all of the config data has been cached,
        # because it will have been looked up as part of the get_actions method
        # when the menu asked for actions, so getting the manager and all of the
        # config data will be essentially free.
        manager = self._get_toolkit_manager()
        with self._LOCK:
            manager.bundle_cache_fallback_paths = self._engine.sgtk.bundle_cache_fallback_paths
            all_pc_data = self._get_pipeline_configuration_data(
                manager,
                project_entity,
                data,
            )

        python_exe = self._get_python_interpreter(all_pc_data[config_entity["id"]]["descriptor"])
        logger.debug("Python executable: %s", python_exe)

        args = [python_exe, script, args_file]
        logger.debug("Subprocess arguments: %s", args)

        # Ensure the credentials are still valid before launching the command in
        # a separate process. We need do to this in advance because the process
        # that will be launched might not have PySide and as such won't be able
        # to prompt the user to re-authenticate.

        # If you are running in Shotgun Desktop 1.0.2 there is no authenticated
        # user, only a script user, so skip this.
        if sgtk.get_authenticated_user():
            sgtk.get_authenticated_user().refresh_credentials()

        retcode, stdout, stderr = command.Command.call_cmd(args)

        if retcode != 0:
            logger.error("Command failed: %s", args)
            logger.error("Failed command stdout: %s", stdout)
            logger.error("Failed command stderr: %s", stderr)
            self.host.reply(
                dict(
                    retcode=constants.COMMAND_FAILED,
                    out=stdout,
                    err=stderr,
                )
            )
            return

        filtered_output = []

        # We need to filter stdout before we send it to the client.
        # We look for lines that we know came from the custom log
        # handler that the execute_command script builds, and we
        # remove that header from those lines and keep them so that
        # they're passed up to the client.
        tag = constants.LOGGING_PREFIX
        tag_length = len(tag)

        # We check both stdout and stderr. We identify lines that start with
        # our tag, and if we find one, we remove the tag, and then base64
        # decode the rest of the message. The message is encoded this way
        # because it collapses multi-line log messages into a single line
        # of text. This is important, because there's only one tag per log
        # message, and we would otherwise filter out everything in the log
        # message that wasn't on the first line of text before any newlines.
        for line in stdout.split("\n") + stderr.split("\n"):
            if line.startswith(tag):
                filtered_output.append(base64.b64decode(line[tag_length:]))

        filtered_output_string = "\n".join(filtered_output)
        logger.debug("Command execution complete.")

        self.host.reply(
            dict(
                retcode=constants.COMMAND_SUCCEEDED,
                out=filtered_output_string,
                err="",
            ),
        )

    @sgtk.LogManager.log_timing
    def get_actions(self, data):
        """
        RPC method that sends back a dictionary containing engine commands
        for each pipeline configuration associated with the project.

        :param dict data: The data passed down by the client. At a minimum,
            the dict should contain the following keys: project_id, entity_id,
            entity_type, pipeline_configs, and user.
        """
        # When the v2 protocol is being used, the Shotgun web app makes use of
        # Javascript Promises to handle the reply from the server, whether there
        # is success or failure. When getting actions, we want to make sure that
        # if there was some kind of unhandled exception that there is a proper
        # reply to the client so that the Promise can be kept or broken, as is
        # appropriate.
        try:
            self._get_actions(data)
        except Exception:
            import traceback
            self.host.reply(
                dict(
                    err="Failed to get actions: %s" % traceback.format_exc(),
                    retcode=constants.CACHING_ERROR,
                    out="",
                ),
            )

    def _get_actions(self, data):
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
            if not data.get("entity_type"):
                # There's likely some gap in the pre-caching logic that's run on
                # toolkit action menu init that's causing either an empty string
                # or an undefined value for the entity type. We can't really do
                # anything here in that case, so it's best to reply with an error
                # that explains as best we can what's happened.
                self.host.reply(
                    dict(
                        err="Toolkit received no entity type for this menu -- no actions can be returned!",
                        retcode=constants.CACHING_ERROR,
                        out="",
                    ),
                )
                return
            elif data["entity_type"] == "Project":
                data["entity_id"] = data["project_id"]
            else:
                temp_entity = self._engine.shotgun.find_one(
                    data["entity_type"],
                    [["project", "is", dict(type="Project", id=data["project_id"])]],
                )

                if temp_entity:
                    data["entity_id"] = temp_entity["id"]
                else:
                    # This is the case if we're on an entity page, but there
                    # are no entities that exist. The page's pre-caching call
                    # here can't proceed, but we can let it know what the situation
                    # is via the retcode, and the tank_action_menu will be sure to
                    # re-query the actions if an entity is created and the menu
                    # shown.
                    self.host.reply(
                        dict(
                            err="No entity existed when actions were requested. Please refresh the page.",
                            retcode=constants.CACHING_NOT_COMPLETED,
                            out="Please refresh the page to get Toolkit actions.",
                        ),
                    )
                    return

        # It's possible that we got multiple entities from the client, which
        # would be the result of multiple entities being selected in the web
        # interface. Regardless of that, as far as getting a list of actions
        # is concerned, we only need one. As such, we just take the first one
        # off the list.
        project_entity, entities = self._get_entities_from_payload(data)
        entity = entities[0]
        manager = self._get_toolkit_manager()

        with self._LOCK:
            manager.bundle_cache_fallback_paths = self._engine.sgtk.bundle_cache_fallback_paths
            all_pc_data = self._get_pipeline_configuration_data(
                manager,
                project_entity,
                data,
            )

        # The first thing we do is check to see if we're dealing with a
        # classic SGTK setup. In that case, we're going to short-circuit
        # the get_actions call and go into a legacy setup that makes use
        # of the "tank" command by way of this api's process_manager.
        did_legacy_lookup = False
        all_actions = dict()
        config_names = []
        legacy_config_ids = []

        if self._allow_legacy_workaround:
            config_entities = []
            legacy_config_data = dict()

            for config_id, config_data in all_pc_data.iteritems():
                config = config_data["entity"]

                if config["descriptor"].required_storages:
                    # We're using os.path.dirname to chop the last directory off
                    # the end of the config descriptor path. This is because that
                    # path is routed to <root>/config, while the v1 api is just
                    # wanting the root path where the tank command lives.
                    legacy_config_data[config["name"]] = (
                        config["descriptor"].get_path(),
                        config
                    )

                    legacy_config_ids.append(config_id)

            # We're going to remove this config from the data structure
            # housing all of the project's pipeline configuration information.
            # With this, we can allow the legacy pathway to handle the classic
            # configs, while allowing descriptor-driven configs to run through
            # the v2 flow.
            for config_id in legacy_config_ids:
                del all_pc_data[config_id]

            # If there are any classic configs, then we use the legacy code
            # path.
            if legacy_config_data:
                logger.debug("Classic SGTK config(s) found, proceeding with legacy code path.")
                self._legacy_process_configs(
                    legacy_config_data,
                    entity["type"],
                    project_entity["id"],
                    all_actions,
                    config_names,
                )
                did_legacy_lookup = True

        with self._db_connect() as (connection, cursor):
            for pc_id, pc_data in all_pc_data.iteritems():
                pipeline_config = pc_data["entity"]

                # The hash that acts as the key we'll use to look up our cached
                # data will be based on the entity type and the pipeline config's
                # descriptor uri. We can get the descriptor from the toolkit
                # manager and pass that through along with the entity type from SG
                # to the core hook that computes the hash.
                pc_descriptor = pipeline_config["descriptor"]

                # We'll rebuild this pipeline_config dict to only include the keys
                # that we know we want to pass back to the client. In the event that
                # the interface to getting these config dicts changes in the future,
                # it will help us keep from passing back uneeded data or, even worse,
                # data that can't be serialized, which would cause an exception.
                pipeline_config = dict(
                    id=pipeline_config["id"],
                    type=pipeline_config.get("type", "PipelineConfiguration"),
                    name=pipeline_config.get("name", "Primary"),
                )
                all_pc_data[pc_id]["entity"] = pipeline_config

                # We start with an empty action set for this config. If we end up finding
                # finding stuff for this entity type in this config, then the empty
                # entry here will be replaced prior to replying to the client.
                all_actions[pipeline_config["name"]] = dict(
                    actions=[],
                    config=pipeline_config,
                )

                # Let's see if this is even an entity type that we need to worry
                # about. If it isn't, we can just move on to the next config.
                #
                # Note: The entity type whitelist contains entity type names that
                # have been lower cased.
                supported_entity_type = data["entity_type"].lower() in self._get_entity_type_whitelist(
                    data.get("project_id"),
                    pc_descriptor,
                )

                if not supported_entity_type and not did_legacy_lookup:
                    logger.debug(
                        "Entity type %s is not supported by %r, no actions will be returned.",
                        data["entity_type"],
                        pc_descriptor,
                    )
                    continue

                # In all cases except for Task entities, we'll already have a
                # lookup hash computed. If we're dealing with a Task, though,
                # it'll be a None and we'll need to compute it live. This is
                # because the lookup hash depends on what the specific Task
                # entity we're dealing with is linked to.
                try:
                    lookup_hash = pc_data["lookup_hash"] or self._get_lookup_hash(
                        pc_descriptor.get_uri(),
                        project_entity,
                        entity["type"],
                        entity["id"],
                    )
                except TankTaskNotLinkedError:
                    # If we're dealing with a Task entity, it needs to be linked
                    # to something. If it's not, then we have nothing to pass
                    # back to the client, so we should inform the user as to
                    # how to proceed.
                    logger.debug("Task entity %s is not linked to an entity.", entity)
                    self.host.reply(
                        dict(
                            err="Link this Task to an entity and refresh to get Toolkit actions!",
                            retcode=constants.CACHING_ERROR,
                            out="",
                        ),
                    )
                    return

                pc_data["lookup_hash"] = lookup_hash
                pc_data["descriptor"] = pc_descriptor
                contents_hash = pc_data["contents_hash"]
                cached_data = []

                # We lock here because we cannot allow concurrent bootstraps to
                # occur. We do it this early because we also want others to wait
                # in the event that we end up caching what they need while they
                # wait for the lock to be released.
                with self._LOCK:
                    logger.debug("Querying: %s", lookup_hash)

                    try:
                        cursor.execute(
                            "SELECT commands, contents_hash FROM engine_commands WHERE lookup_hash=?",
                            (lookup_hash,)
                        )
                        cached_data = list(cursor.fetchone() or [])
                    except sqlite3.OperationalError:
                        # This means the sqlite database hasn't been setup at all.
                        # In that case, we just continue on with cached_data set
                        # to an empty list, which will cause the caching subprocess
                        # to be spawned, which will setup the database and populate
                        # with the data we need. The behavior as a result of this
                        # is the same as if we ended up with a cache miss or an
                        # invalidated result due to a contents_hash mismatch.
                        logger.debug(
                            "Cache query failed due to missing table. "
                            "Triggering caching subprocess..."
                        )

                    try:
                        if cached_data:
                            # Cache hit.
                            cached_contents_hash = cached_data[1]

                            # Check to see if the current hash we created matches
                            # that of the cached entry. If it matches then we know
                            # that the data is up to date and that we can use it.
                            if str(contents_hash) == str(cached_contents_hash):
                                logger.debug("Cache is up to date.")
                                logger.debug("Cache key was %s", lookup_hash)
                                logger.debug("Contents hash (computed) was %s", contents_hash)
                                logger.debug("Contents hash (cached) was %s", cached_contents_hash)

                                actions = self._process_commands(
                                    commands=cPickle.loads(str(cached_data[0])),
                                    project=project_entity,
                                    entities=entities,
                                )

                                logger.debug("Actions found in cache: %s", actions)

                                all_actions[pipeline_config["name"]] = dict(
                                    actions=self._filter_by_project(
                                        actions,
                                        self._get_software_entities(),
                                        project_entity,
                                    ),
                                    config=pipeline_config,
                                )
                                logger.debug("Actions after project filtering: %s", actions)
                            else:
                                # The hashes didn't match, so we know we need to
                                # re-cache. Once we do that, we can just call the
                                # get_actions method again with the same payload.
                                logger.debug("Cache is out of date, recaching...")
                                self._cache_actions(data, pc_data)
                                self._get_actions(data)
                                return
                        else:
                            # Cache miss.
                            logger.debug("Commands not found in cache, caching now...")
                            self._cache_actions(data, pc_data)
                            self._get_actions(data)
                            return
                    except TankCachingSubprocessFailed as exc:
                        logger.error(str(exc))
                        raise
                    except TankCachingEngineBootstrapError:
                        logger.error(
                            "The Shotgun engine failed to initialize in the caching "
                            "subprocess. This most likely corresponds to a configuration "
                            "problem in the config %r as it relates to entity type %s." %
                            (pc_descriptor, entity["type"])
                        )
                        continue

        # Combine the config names processed by the v2 flow with those handled
        # by the legacy pathway.
        config_names = config_names + [p["entity"]["name"] for p in all_pc_data.values()]

        self.host.reply(
            dict(
                err="",
                retcode=constants.SUCCESSFUL_LOOKUP,
                actions=all_actions,
                pcs=config_names,
            ),
        )

    def open(self, data):
        """
        Open a file on localhost.

        :param dict data: Message payload.
        """
        try:
            # Retrieve filepath.
            filepath = data.get("filepath")
            result = self.process_manager.open(filepath)

            # Send back information regarding the success of the operation.
            reply = {}
            reply["result"] = result

            self.host.reply(reply)
        except Exception, e:
            self.host.report_error(e.message)

    def pick_file_or_directory(self, data):
        """
        Pick single file or directory.

        :param dict data: Message payload. (no data expected)
        """
        files = self.process_manager.pick_file_or_directory(False)
        self.host.reply(files)

    def pick_files_or_directories(self, data):
        """
        Pick multiple files or directories.

        :param dict data: Message payload. (no data expected)
        """
        files = self.process_manager.pick_file_or_directory(True)
        self.host.reply(files)

    ###########################################################################
    # Context managers

    @contextlib.contextmanager
    def _db_connect(self):
        """
        Context manager that initializes a DB connection on enter and
        disconnects on exit.
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

        with connection:
            with contextlib.closing(connection.cursor()) as cursor:
                yield (connection, cursor)

    def _compute_sys_path(self):
        """
        :returns: Path to the current core.
        """
        # While core swapping, the Python path is not updated with the new core's Python path,
        # so make sure the current core is at the front of the Python path for out subprocesses.
        python_folder = sgtk.bootstrap.ToolkitManager.get_core_python_path()
        logger.debug("Adding %s to sys.path for subprocesses.", python_folder)
        return [python_folder] + sys.path

    ###########################################################################
    # Internal methods

    @sgtk.LogManager.log_timing
    def _cache_actions(self, data, config_data):
        """
        Triggers the caching or recaching of engine commands.

        :param dict data: The data passed down from the wss client.
        :param dict config_data: A dictionary that contains, at a minimum,
            "lookup_hash", "contents_hash", "descriptor", and "entity" keys.
        """
        logger.debug("Caching engine commands...")

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "cache_commands.py"
        )

        logger.debug("Executing script: %s", script)
        descriptor = config_data["descriptor"]

        # We'll need the Python executable when we shell out. We want to make sure
        # we use the Python defined in the config's interpreter config file.
        python_exe = self._get_python_interpreter(descriptor)
        logger.debug("Python executable: %s", python_exe)

        arg_config_data = dict(
            lookup_hash = config_data["lookup_hash"],
            contents_hash=config_data["contents_hash"],
            entity=config_data["entity"],
        )

        args_file = self._get_arguments_file(
            dict(
                cache_file=self._cache_path,
                data=data,
                sys_path=self._compute_sys_path(),
                base_configuration=constants.BASE_CONFIG_URI,
                engine_name=constants.ENGINE_NAME,
                config_data=arg_config_data,
                config_is_mutable=(descriptor.is_immutable() == False),
                bundle_cache_fallback_paths=self._engine.sgtk.bundle_cache_fallback_paths
            )
        )

        args = [python_exe, script, args_file]
        logger.debug("Command arguments: %s", args)

        retcode, stdout, stderr = command.Command.call_cmd(args)

        if retcode == 0:
            logger.debug("Command stdout: %s", stdout)
            logger.debug("Command stderr: %s", stderr)
        elif retcode == constants.ENGINE_INIT_ERROR_EXIT_CODE:
            logger.debug("Caching subprocess reported a problem buring bootstrap.")
            raise TankCachingEngineBootstrapError("%s\n\n%s" % (stdout, stderr))
        else:
            logger.error("Command failed: %s", args)
            logger.error("Failed command stdout: %s", stdout)
            logger.error("Failed command stderr: %s", stderr)
            logger.error("Failed command retcode: %s", retcode)
            raise TankCachingSubprocessFailed("%s\n\n%s" % (stdout, stderr))

        logger.debug("Caching complete.")

    def _get_python_interpreter(self, descriptor):
        """
        Retrieves the python interpreter from the configuration. Returns the
        current python interpreter if no interpreter was specified.
        """
        try:
            path_to_python = descriptor.python_interpreter
        except TankFileDoesNotExistError:
            if sys.platform == "darwin":
                path_to_python = os.path.join(sys.prefix, "bin", "python")
            elif sys.platform == "win32":
                path_to_python = os.path.join(sys.prefix, "python.exe")
            else:
                path_to_python = os.path.join(sys.prefix, "bin", "python")
        return path_to_python

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
            logger,
            self._engine.sgtk,
            pc_entity_id,
            user_id,
            new_name,
            new_path_linux,
            new_path_mac,
            new_path_windows,
            sgtk.pipelineconfig_utils.is_localized(data["pc_root_path"]),
        )

        # Once the config is cloned, we need to invalidate the in-memory cache
        # that contains the PipelineConfiguration entities queried from SG.
        del self._cache[self.PIPELINE_CONFIGS]

    @sgtk.LogManager.log_timing
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
            # The engine_name property of an engine command is defined by
            # tk-multi-launchapp, and corresponds to the engine that provided
            # the information necessary to register the launcher. If the action
            # doesn't include that key, then it means the underlying engine
            # command did not provide that property, and as such is not a
            # launcher. Similarly, if it's set to None then the same applies
            # and we don't need to test this action for filtering purposes.
            if action.get("engine_name") is None:
                continue

            # We're only interested in entities that are referring to the
            # same engine as is recorded in the action dict.
            associated_sw = [s for s in sw_entities if s["engine"] == action["engine_name"]]

            # Check the project against the projects list for matching Software
            # entities. If a Software entity's projects list is empty, then there
            # is no filtering to be done, as it's accepted by all projects.
            for sw in associated_sw:
                for sw_project in sw.get("projects", []):
                    if sw_project["id"] != project["id"]:
                        logger.debug("Action %s filtered out due to SW entity projects.", action)
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

    @sgtk.LogManager.log_timing
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

        if config_descriptor and config_descriptor.is_immutable() == False:
            yml_files = self._get_yml_file_data(config_descriptor)

            if yml_files is not None:
                hashable_data["modtimes"] = yml_files

        # Dict objects aren't hashable directly by way of hash() or the md5
        # module, so we need to create a stable string representation of the
        # data structure. The quickest way to do that is to json encode
        # everything, sorting on keys to stabilize the results.
        json_data = json.dumps(
            hashable_data,
            sort_keys=True,
            default=self.__json_default,
        )

        logger.debug("Contents data to be used in hash generation: %s", json_data)

        hash_data = hashlib.md5()
        hash_data.update(json_data)
        return hash_data.digest()

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
                project=project_entity,
            )
            return (project_entity, [entity])
        elif "entity_ids" in data:
            entities = []

            for entity in data["entity_ids"]:
                # Did we get an entity list, or a list of entity ids?
                if isinstance(entity, dict):
                    if "project" not in entity:
                        entity["project"] = project_entity

                    entities.append(entity)
                else:
                    entities.append(
                        dict(
                            type=data["entity_type"],
                            id=entity,
                            project=project_entity,
                        )
                    )
            return (project_entity, entities)
        else:
            raise RuntimeError("Unable to determine an entity from data: %s" % data)

    @sgtk.LogManager.log_timing
    def _get_entity_type_whitelist(self, project_id, config_descriptor):
        """
        Gets a set of entity types that are supported by the browser
        integration. This set is built from a list of constant entity
        types, plus all entity types that a PublishedFile entity is
        allowed to link to, per the current site's schema.

        :param int project_id: The associated project entity id. The
            schema is queried by project, as project-level masking of the
            PublishedFile entity's linkable types is possible. If no project
            is given, the site-level schema is queried instead.
        :param config_descriptor: The Descriptor object for the pipeline
            configuration being processed. This is used to get the config's
            root path if it is determined that the config is mutable, in which
            case the entity type whitelist will include those entities that
            have an associated shotgun_{entity_type}.yml file.

        :returns: A set of lowercased string entity types.
        :rtype: set
        """
        if project_id is None:
            logger.debug("Project id is None, looking up site schema.")
            project_entity = None
        else:
            project_entity = dict(type="Project", id=project_id)
            logger.debug("Looking up schema for project %s", project_entity)

        config_root = config_descriptor.get_path()
        cache_is_initialized = self.ENTITY_TYPE_WHITELIST in self._cache
        config_in_cache = config_root in self._cache.get(self.ENTITY_TYPE_WHITELIST, dict())

        if not cache_is_initialized or not config_in_cache:
            # We're storing lowercased type names because we have the possibility
            # of also merging in types defined as shotgun_xxx.yml files in a config's
            # environment. Those files contain entity type names that are lower cased,
            # so it's easiest just to do everything that way.
            type_whitelist = set([t.lower() for t in constants.BASE_ENTITY_TYPE_WHITELIST])

            # This will only ever happen once per unique connection. That means
            # on page refresh it happens, but not every time menu actions are
            # requested.
            #
            # The conditional here is simply for the case of test suites. At this
            # time, Mockgun's schema_field_read method doesn't accept a project_entity
            # argument, and when running unit tests it's really not needed anyway.
            if project_entity is not None:
                schema = self._engine.shotgun.schema_field_read(
                    constants.PUBLISHED_FILE_ENTITY,
                    field_name="entity",
                    project_entity=project_entity,
                )
            else:
                schema = self._engine.shotgun.schema_field_read(
                    constants.PUBLISHED_FILE_ENTITY,
                    field_name="entity",
                )
            linkable_types = schema["entity"]["properties"]["valid_types"]["value"]
            linkable_types = [t.lower() for t in linkable_types]
            type_whitelist = type_whitelist.union(set(linkable_types))

            # It's less likely that an immutable config will contain legacy shotgun_xxx.yml
            # environment files that we need to take into account. However, it's possible
            # and we have seen the Studio team internal to Shotgun tinkering with some
            # configs built this way. As such, the below logic will check for shotgun_xxx.yml
            # files regardless of whether this is an immutable config or not.
            #
            # Matches something like "/shotgun/config/env/shotgun_shot.yml" and
            # extracts "shot" from the yml file basename.
            match_re = re.compile(r".+shotgun_([^.]+)[.]yml$")

            for yml_file in self._get_yml_file_data(config_descriptor).keys():
                logger.debug("Checking %s for entity type whitelisting...", yml_file)
                match = re.match(match_re, yml_file)
                if match:
                    logger.debug(
                        "File %s is a shotgun_xxx.yml file, extracting entity type...",
                        yml_file,
                    )

                    # Group 0 is the entire match, group 1 is the extracted
                    # entity type name.
                    type_name = match.group(1)

                    logger.debug(
                        "Adding entity type %s to whitelist from %s.",
                        type_name,
                        yml_file,
                    )
                    type_whitelist.add(type_name)

            logger.debug("Entity-type whitelist for project %s: %s", project_id, type_whitelist)
            self._cache.setdefault(self.ENTITY_TYPE_WHITELIST, dict())[config_root] = type_whitelist

        # We'll copy the data out of the cache, as we do elsewhere. This is
        # just to isolate the cache from any changes to the returned data
        # after it's returned.
        return copy.deepcopy(self._cache[self.ENTITY_TYPE_WHITELIST][config_root])

    @sgtk.LogManager.log_timing
    def _get_lookup_hash(self, config_uri, project, entity_type, entity_id):
        """
        Computes a unique key for a row in a cache database for the given
        pipeline configuration descriptor and entity type.

        :param str config_uri: The pipeline configuration's descriptor uri.
        :param dict project: The project entity.
        :param str entity_type: The entity type.
        :param int entity_id: The entity id.

        :returns: The computed lookup hash.
        :rtype: str
        """
        cache_key = self._bundle.execute_hook_method(
            "browser_integration_hook",
            "get_cache_key",
            config_uri=config_uri,
            project=project,
            entity_type=entity_type
        )

        # Tasks are a bit special. We lookup actions by the Task entity type,
        # as is normal, but we cache it including the parent entity's type to
        # ensure that we allow for different actions to be configured for Tasks
        # linked to different parent entity types(ie: Shot vs. Asset). This has
        # no impact on legacy configurations that contain a shotgun_task.yml file,
        # but it does when tk-shotgun is configured in a non-shotgun_xxx.yml
        # environment that the config's pick_environment hook recognizes as a
        # Task entity's target environment. In that case, it would be possible
        # to configure different engine commands for tk-shotgun when a Task is
        # linked to a Shot versus when it's linked to an Asset.
        if entity_type == "Task":
            logger.debug("Task entity detected, looking up parent entity...")
            parent_entity_type = self._get_task_parent_entity_type(entity_id)
            logger.debug("Task entity's parent entity type: %s", entity_type)
            cache_key += parent_entity_type
            logger.debug("Task entity's cache key is: %s", cache_key)

        return cache_key

    @sgtk.LogManager.log_timing
    def _get_pipeline_configuration_data(self, manager, project_entity, data):
        """
        Gathers all of the necessary data pertaining to the project's pipeline
        configurations. This includes the PipelineConfiguration entity, the
        contents and lookup hashes, and the associated descriptor object.

        :param manager: A ToolkitManager.
        :param dict project_entity: The Project entity dict.
        :param dict data: The payload from the client.

        :returns: A dictionary, keyed by PipelineConfiguration entity id, that
            contains dictionaries with "contents_hash", "lookup_hash",
            "descriptor", and "entity" keys.
        :rtype: dict
        """
        entity_type = data["entity_type"]
        cache = self._cache

        config_data_in_cache = self.CONFIG_DATA in cache

        if config_data_in_cache and \
           entity_type in cache[self.CONFIG_DATA] and \
           project_entity["id"] in cache[self.CONFIG_DATA][entity_type]:
            logger.debug("%s pipeline config data found for %s", entity_type, self._wss_key)
        else:
            config_data = dict()

            pipeline_configs = self._get_pipeline_configurations(
                manager,
                project_entity,
            )

            # If there are no configs that we got back, then we just operate on
            # a dummy "Primary" entity with no id. This will cause the manager
            # to have its pipeline_configuration property set to None, which
            # will trigger the config resolution to use the base_configuration,
            # which is the desired behavior.
            if not pipeline_configs:
                pipeline_configs = [
                    dict(
                        id=None,
                        name="Primary",
                        descriptor=manager.resolve_descriptor(project_entity),
                    ),
                ]

            for pipeline_config in pipeline_configs:
                logger.debug("Processing config: %s", pipeline_config)

                # We're not going to need the project field in the config
                # entity, since we already know what Project we're dealing
                # with. In the event that the project name has non-ascii
                # characters in it, it could also cause unicode decode issues
                # later on. Best to just ditch it now.
                if "project" in pipeline_config:
                    del pipeline_config["project"]

                # The hash that acts as the key we'll use to look up our cached
                # data will be based on the entity type and the pipeline config's
                # descriptor uri. We can get the descriptor from the toolkit
                # manager and pass that through along with the entity type from SG
                # to the core hook that computes the hash.
                manager.pipeline_configuration = pipeline_config["id"]
                pc_descriptor = pipeline_config["descriptor"]

                if pc_descriptor is None:
                    logger.warning(
                        "Unable to resolve config descriptor, skipping: %r",
                        pipeline_config,
                    )
                    continue

                if not pc_descriptor.is_immutable() and pc_descriptor.get_path() is None:
                    logger.warning(
                        "Config does not point to a valid location on disk, skipping: %r",
                        pipeline_config,
                    )
                    continue

                logger.debug("Resolved config descriptor: %r", pc_descriptor)
                pc_key = pc_descriptor.get_uri()

                pc_data = dict()
                pc_data["contents_hash"] = self._get_contents_hash(
                    pc_descriptor,
                    self._get_site_state_data(),
                )

                # Tricky bit here. We don't want to pre-compute the lookup hash
                # if this is a Task entity. This is because Tasks can be linked
                # to Shots or Assets, and we need to differentiate between the
                # two. Whether we get Shot or Asset actions depends on the Task
                # in question, and so the lookup hash needs to be computed live.
                if data["entity_type"] == "Task":
                    pc_data["lookup_hash"] = None
                else:
                    pc_data["lookup_hash"] = self._get_lookup_hash(
                        pc_key,
                        project_entity,
                        data["entity_type"],
                        data["entity_id"],
                    )
                pc_data["descriptor"] = pc_descriptor
                pc_data["entity"] = pipeline_config
                config_data[pipeline_config["id"]] = pc_data

            # If we already have cached other entity types, we'll have the
            # config_data key already present in the cache. In that case, we
            # just need to update it's contents with the new data. Otherwise,
            # we populate it from scratch.
            cache.setdefault(self.CONFIG_DATA, dict())
            cache[self.CONFIG_DATA].setdefault(entity_type, dict())
            cache[self.CONFIG_DATA][entity_type].setdefault(project_entity["id"], dict()).update(config_data)

        # We'll deepcopy the data before returning it. That will ensure that
        # any destructive operations on the contents won't bubble up to the
        # cache.
        return copy.deepcopy(cache[self.CONFIG_DATA][entity_type][project_entity["id"]])

    @sgtk.LogManager.log_timing
    def _get_pipeline_configurations(self, manager, project):
        """
        Gets all PipelineConfiguration entities for the given project.

        :param bsm manager: The bootstrap toolkit manager object.
        :type bsm: :class:`~sgtk.bootstrap.ToolkitManager`
        :param dict project: The project entity.

        :returns: A list of PipelineConfiguration entity dictionaries.
        :rtype: list
        """
        # The in-memory cache is keyed by the wss_key that is unique to each
        # wss connection. If we've already queried and cached pipeline configs
        # for the current wss connection, then we can just return that back to
        # the caller.
        if self.PIPELINE_CONFIGS not in self._cache:
            self._cache[self.PIPELINE_CONFIGS] = dict()

        # The configs are stored by project id. We can pull the dict out of the
        # cache and check to see if our project has already been added. If it
        # has then we return it back to the caller. If not, we query what we
        # need and cache the results for next time.
        pc_data = self._cache[self.PIPELINE_CONFIGS]

        if project["id"] not in pc_data:
            pc_data[project["id"]] = manager.get_pipeline_configurations(
                project=project,
            )
        else:
            logger.debug(
                "Cached PipelineConfiguration entities found for %s", self._wss_key
            )

        # We'll deepcopy the data before returning it. That will ensure that
        # any destructive operations on the contents won't bubble up to the
        # cache.
        return copy.deepcopy(pc_data[project["id"]])

    @sgtk.LogManager.log_timing
    def _get_site_state_data(self):
        """
        Gets state-related data for the site. Exactly what data this is depends
        on the "browser_integration" hook's "get_site_state_data" method,
        which returns a list of dicts passed to the Shotgun Python API's find
        method as kwargs. The data returned by this method is cached based on
        the WSS connection key provided to the API's constructor at instantiation
        time. This means that this data is queried from Shotgun only once per
        unique WSS connection.

        :returns: A list of Shotgun entity dictionaries.
        :rtype: list
        """
        if self.SITE_STATE_DATA not in self._cache:
            self._cache[self.SITE_STATE_DATA] = self._get_software_entities()

            requested_data_specs = self._bundle.execute_hook_method(
                "browser_integration_hook",
                "get_site_state_data",
            )

            for spec in requested_data_specs:
                entities = self._engine.shotgun.find(**spec)
                self._cache[self.SITE_STATE_DATA].extend(entities)
        else:
            logger.debug("Cached site state data found for %s", self._wss_key)

        # We'll deepcopy the data before returning it. That will ensure that
        # any destructive operations on the contents won't bubble up to the
        # cache.
        return copy.deepcopy(self._cache[self.SITE_STATE_DATA])

    @sgtk.LogManager.log_timing
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
        cache = self._cache

        if self.SOFTWARE_ENTITIES not in cache:
            logger.debug(
                "Software entities have not been cached for this connection, querying..."
            )

            cache[self.SOFTWARE_ENTITIES] = self._engine.shotgun.find(
                "Software",
                [],
                fields=self.SOFTWARE_FIELDS,
            )
        else:
            logger.debug("Cached software entities found for %s", self._wss_key)

        # We'll deepcopy the data before returning it. That will ensure that
        # any destructive operations on the contents won't bubble up to the
        # cache.
        return cache[self.SOFTWARE_ENTITIES]

    @sgtk.LogManager.log_timing
    def _get_task_parent_entity_type(self, task_id):
        """
        Gets the Task entity's parent entity type.

        :param int task_id: The id of the Task entity to find the parent of.

        :returns: The Task's parent entity type.
        :rtype: str
        """
        cache = self._cache

        if self.TASK_PARENT_TYPES in cache and task_id in cache[self.TASK_PARENT_TYPES]:
            logger.debug("Parent entity type found in cache for Task %s.", task_id)
        else:
            context = sgtk.context.from_entity(
                self._engine.sgtk,
                "Task",
                task_id,
            )

            if context.entity is None:
                raise TankTaskNotLinkedError("Task is not linked to an entity.")
            else:
                entity_type = context.entity["type"]
            cache.setdefault(self.TASK_PARENT_TYPES, dict())[task_id] = entity_type

        return cache[self.TASK_PARENT_TYPES][task_id]

    def _get_toolkit_manager(self):
        """
        Gets an initialized ToolkitManager object.

        :returns: A ToolkitManager object.
        """
        if self.TOOLKIT_MANAGER is None:
            self.TOOLKIT_MANAGER = sgtk.bootstrap.ToolkitManager()
            self.TOOLKIT_MANAGER.allow_config_overrides = False
            self.TOOLKIT_MANAGER.plugin_id = "basic.shotgun"
            self.TOOLKIT_MANAGER.base_configuration = constants.BASE_CONFIG_URI

        return self.TOOLKIT_MANAGER

    @sgtk.LogManager.log_timing
    def _get_yml_file_data(self, config_descriptor):
        """
        Gets environment yml file paths and their associated mtimes for the
        given pipeline configuration descriptor object. The data will be looked
        up once per unique wss connection and cached.

        ..Example:
            {
                "/shotgun/my_project/config": {
                    "/shotgun/my_project/config/env/project.yml": 1234567,
                    ...
                },
                ...
            }

        :param config_descriptor: The descriptor object for the config to get
            yml file data for.

        :returns: A dictionary keyed by yml file path, set to the file's mtime
            at the time the data was cached.
        :rtype: dict
        """
        root_path = config_descriptor.get_path()

        if self.YML_FILE_DATA not in self._cache or root_path not in self._cache[self.YML_FILE_DATA]:
            # We do a shallow scan here of the bare minimum of yml files due
            # to speed concerns when network file servers are in use. We support
            # tk-shotgun configured in either the shotgun or non-shotgun yml
            # so we will stat all of the top level env files that we find. Note
            # that this means we are not covering included yml files, but we
            # accept that for the sake of speed.
            yml_files = dict()
            config_path = os.path.join(root_path, "env")

            if config_path is not None:
                logger.debug(
                    "Config %s is mutable -- environment file mtimes will be used to determine cache validity.",
                    config_path,
                )

                for file_path in glob.glob(os.path.join(config_path, "*.yml")):
                    yml_files[file_path] = os.path.getmtime(file_path)

            logger.debug(
                "Contents hash computed using %s yml files -- shallow scan, no subdirectories.",
                len(yml_files),
            )

            logger.debug("Files checked for mtime: %s", sorted(yml_files.keys()))

            self._cache.setdefault(self.YML_FILE_DATA, dict())[root_path] = yml_files
        else:
            logger.debug("Cached yml file data found for %r.", config_descriptor)

        return self._cache[self.YML_FILE_DATA].get(root_path)

    def _legacy_get_project_actions(self, config_paths, project_id):
        """
        Gets all actions for all shotgun_xxx environments for the project and
        caches them in memory, keyed by the unique session key provided by
        the websocket server.

        :param list config_paths: A list of string file paths to the root
            directory of each pipeline configuration to get actions for.

        :returns: All commands for all shotgun_xxx environments for all
            requested pipeline configs.
        :rtype: dict
        """
        # The in-memory cache is keyed by the wss_key that is unique to each
        # wss connection.
        cache_not_initialized = self.LEGACY_PROJECT_ACTIONS not in self._cache

        if cache_not_initialized:
            self._cache[self.LEGACY_PROJECT_ACTIONS] = dict()

        project_not_cached = project_id not in self._cache[self.LEGACY_PROJECT_ACTIONS]

        if project_not_cached:
            self._cache[self.LEGACY_PROJECT_ACTIONS][project_id] = self.process_manager.get_project_actions(
                config_paths,
            )

        # We'll deepcopy the data before returning it. That will ensure that
        # any destructive operations on the contents won't bubble up to the
        # cache.
        return copy.deepcopy(self._cache[self.LEGACY_PROJECT_ACTIONS][project_id])

    def _legacy_process_configs(self, config_data, entity_type, project_id, all_actions, config_names):
        """
        Processes the raw engine command data coming from the tank command
        and organizes it into the data structure expected from the v2 wss
        server by the client. This method acts as the adapter between the
        legacy v1 API method of getting toolkit actions and the v2 menu
        logic in the Shotgun web app versions 7.2.0+.

        :param dict config_data: A dictionary, keyed by PipelineConfiguration
            entity name, containing a tuple of config root path and config
            entity dict, in that order.
        :param str entity_type: The entity type that we're getting actions
            for.
        :param int project_id: The Project entity's id. This is used to key the
            in-memory cache of project actions.
        :param dict all_actions: The dict object to add the discovered actions
            to.
        :param list config_names: The list object to add processed config names
            to.
        """
        # The config_data is structured as dict(name=(path, entity)), so
        # to extract just the paths, we get index 0 of each tuple stored
        # in the dict.
        config_paths = [p[0] for n, p in config_data.iteritems()]
        project_actions = self._legacy_get_project_actions(config_paths, project_id)

        for config_name, config_data in config_data.iteritems():
            config_path, config_entity = config_data
            commands = []

            # We don't need or want the descriptor object to be sent to the client.
            # Since we're done with this config for this invokation, we can just
            # delete it from the entity dict.
            del config_entity["descriptor"]

            # And since we know this set of actions came from this legacy path, we
            # can go ahead and include some extra data in the config dict that we
            # can key off of when this action is called from the client.
            config_entity[constants.LEGACY_CONFIG_ROOT] = config_path

            try:
                get_actions_data = project_actions[config_path]["shotgun_get_actions"]
            except KeyError:
                logger.debug(
                    "The tank command didn't return any actions for this config: %s",
                    config_path
                )
                continue

            env_file_name = "shotgun_%s.yml" % entity_type.lower()
            raw_actions_data = get_actions_data.get(env_file_name)

            # In the case where the specific shotgun_*.yml environment
            # file we're looking for doesn't exit in the data returned by
            # the tank command, we just skip the config. The reason for this
            # will be that there is not shotgun_<entity_type>.yml file for the
            # entity type requesting actions. In that case, silence is the
            # correct approach, because this isn't considered an error case by
            # the client.
            if raw_actions_data is None:
                logger.debug(
                    "No actions were found for %s in config %s",
                    entity_type,
                    config_path
                )

                all_actions[config_name] = dict(
                    actions=[],
                    config=config_entity,
                )

                continue

            if raw_actions_data["retcode"] != 0:
                logger.error(
                    "A shotgun_get_actions call did not succeed: %s",
                    raw_actions_data
                )

                all_actions[config_name] = dict(
                    actions=[],
                    config=config_entity,
                )

                continue

            config_names.append(config_name)

            # The data returned by the tank command is a newline delimited string
            # that defines rows of ordered data delimited by $ characters.
            try:
                for line in raw_actions_data["out"].split("\n"):
                    action = line.split("$")

                    if action[2] == "":
                        deny_permissions = []
                    else:
                        deny_permissions = action[2].split(",")

                    multi_select = action[3] == "True"

                    commands.append(
                        dict(
                            name=action[0],
                            title=action[1],
                            deny_permissions=deny_permissions,
                            supports_multiple_selection=multi_select,
                            app_name=None, # Not used here.
                            group=None, # Not used here.
                            group_default=None, # Not used here.
                            engine_name=None, # Not used here.
                        )
                    )
            except Exception:
                logger.error("Unable to parse legacy cache file: %s", env_file_name)

            all_actions[config_name] = dict(
                actions=commands,
                config=config_entity,
            )

    def _legacy_sanitize_output(self, out):
        """
        Sanitizes HTML output coming from the Shotgun engine by way of the
        tank command. This method filters out any lines of output not wrapped
        in span tags, and replaces HTML bold tags with Slack-style markdown
        bold syntax.

        :param str out: The raw output string to sanitize.

        :returns: The sanitized output.
        :rtype: str
        """
        sanitized = []
        bold_match = re.compile(r"</*b>")
        span_match = re.compile(r"</*span>")

        for line in out.split("\n"):
            if line.startswith("<span>"):
                line = re.sub(span_match, "", line)
                line = re.sub(bold_match, "*", line)
                sanitized.append(line)

        return "\n".join(sanitized)

    @sgtk.LogManager.log_timing
    def _process_commands(self, commands, project, entities):
        """
        Filters out commands that are not associated with an app, and then
        calls the process_commands methods from the browser_integration
        hook, returning the result.

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
                logger.debug("Keeping command %s -- it has an associated app.", command)
                filtered.append(command)
            else:
                logger.debug(
                    "Command %s filtered out for browser integration.", command
                )

        return self._bundle.execute_hook_method(
            "browser_integration_hook",
            "process_commands",
            commands=filtered,
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

###########################################################################
# Exceptions


class TankTaskNotLinkedError(sgtk.TankError):
    """
    Raised when a Task entity is being processed, but it is not linked to any entity.
    """
    pass


class TankCachingSubprocessFailed(sgtk.TankError):
    """
    Raised when the subprocess used to cache toolkit actions fails unexpectedly.
    """
    pass


class TankCachingEngineBootstrapError(sgtk.TankError):
    """
    Raised when the caching subprocess reports that the engine failed to initialize
    during bootstrap.
    """
    pass

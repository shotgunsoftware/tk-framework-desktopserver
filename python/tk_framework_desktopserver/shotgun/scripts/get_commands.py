# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function
import sys
import json
import traceback
import copy

CORE_INFO_COMMAND = "__core_info"
UPGRADE_CHECK_COMMAND = "__upgrade_check"
LOGGER_NAME = "wss2.cache_commands"
ENGINE_INIT_ERROR_EXIT_CODE = 77
UNRESOLVED_ENV_ERROR_EXIT_CORE = 78


def bootstrap(
    data,
    base_configuration,
    engine_name,
    config_data,
    bundle_cache_fallback_paths,
    user,
):
    """
    Bootstraps into sgtk and returns the resulting engine instance.

    :param dict data: The raw payload send down by the client.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"
    :param dict config_data: All relevant pipeline configuration data. This
        dict is keyed by pipeline config entity id, each containing a dict
        that contains, at a minimum, "entity", "lookup_hash", and
        "contents_hash" keys.
    :param ShotgunUser user: The user that should be used in the bootstrap process

    :returns: Bootstrapped engine instance.
    """
    sgtk.LogManager().initialize_base_file_handler("tk-shotgun")

    logger = sgtk.LogManager.get_logger(LOGGER_NAME)
    logger.debug("Preparing ToolkitManager for bootstrap.")

    entity = dict(
        type=data["entity_type"],
        id=data["entity_id"],
        project=dict(
            type="Project",
            id=data["project_id"],
        ),
    )

    # Setup the bootstrap manager.
    manager = sgtk.bootstrap.ToolkitManager(user)
    manager.caching_policy = manager.CACHE_FULL
    manager.allow_config_overrides = False
    manager.plugin_id = "basic.shotgun"
    manager.base_configuration = base_configuration
    manager.pipeline_configuration = config_data["entity"]["id"]
    manager.bundle_cache_fallback_paths = bundle_cache_fallback_paths

    logger.debug("Starting %s using entity %s", engine_name, entity)
    engine = manager.bootstrap_engine(engine_name, entity=entity)
    logger.debug("Engine %s started using entity %s", engine, entity)

    return engine


def cache(
    cache_file,
    output_file,
    data,
    base_configuration,
    engine_name,
    config_data,
    config_is_mutable,
    bundle_cache_fallback_paths,
    user,
):
    """
    Populates the sqlite cache with a row representing the desired pipeline
    configuration and entity type. If an entry already exists, it is updated.

    :param str cache_file: The path to the sqlite cache file on disk.
    :param str output_file: The path to the file where the results should be stored
    :param dict data: The raw payload send down by the client.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"
    :param dict config_data: All relevant pipeline configuration data. This
        dict is keyed by pipeline config entity id, each containing a dict
        that contains, at a minimum, "entity", "lookup_hash", and
        "contents_hash" keys.
    :param bool config_is_mutable: Whether the pipeline config is mutable. If
        it is, then we include the __core_info and __upgrade_check commands.
    :param ShotgunUser user: The user that should be used in the bootstrap process
    """
    try:
        engine = bootstrap(
            data,
            base_configuration,
            engine_name,
            config_data,
            bundle_cache_fallback_paths,
            user,
        )
    except Exception as e:
        exit_code = ENGINE_INIT_ERROR_EXIT_CODE

        # Store the original exception information so we don't report any possible exceptions from below
        exc_info = sys.exc_info()

        # Try to use a more specific exit code if possible
        try:
            import sgtk

            if isinstance(e, sgtk.platform.TankUnresolvedEnvironmentError):
                exit_code = UNRESOLVED_ENV_ERROR_EXIT_CORE
        except Exception:
            pass

        # We need to give the server a way to know that this failed due
        # to an engine initialization issue. That will allow it to skip
        # this config gracefully and log appropriately.
        print("".join(traceback.format_exception(*exc_info)))
        sys.exit(exit_code)

    # Note that from here on out, we have to use the legacy log_* methods
    # that the engine provides. This is because we're now operating in the
    # tk-core that is configured for the project, which means we can't
    # guarantee that it is v0.18+.
    engine.log_debug("Raw payload from client: %s" % data)

    lookup_hash = config_data["lookup_hash"]
    contents_hash = config_data["contents_hash"]

    engine.log_debug("Processing engine commands...")
    commands = []

    # Slug in the "special" commands that aren't associated with registered
    # engine commands. We only do this for mutable configs, as it doesn't
    # make sense to ask for upgrade information for a config that can't be
    # upgraded.
    engine.log_debug("Configuration data: %s" % config_data)

    if data["entity_type"].lower() == "project" and config_is_mutable:
        engine.log_debug("Registering core and app upgrade commands...")
        commands.extend(
            [
                dict(
                    name="__core_info",
                    title="Check for Core Upgrades...",
                    deny_permissions=["Artist"],
                    app_name="__builtin",
                    group=None,
                    group_default=False,
                    engine_name="tk-shotgun",
                ),
                dict(
                    name="__upgrade_check",
                    title="Check for App Upgrades...",
                    deny_permissions=["Artist"],
                    app_name="__builtin",
                    group=None,
                    group_default=False,
                    engine_name="tk-shotgun",
                ),
            ]
        )
    else:
        if config_is_mutable:
            engine.log_debug(
                "The config is mutable, but this is not a Project entity: "
                "not registering core and app update commands."
            )
        else:
            engine.log_debug(
                "Config is immutable: not registering core and app update commands."
            )

    for cmd_name, data in engine.commands.items():
        engine.log_debug("Processing command: %s" % cmd_name)
        props = data["properties"]
        app = props.get("app")

        if app:
            app_name = app.name
        else:
            app_name = None

        command_data = dict(
            name=cmd_name,
            title=props.get("title", cmd_name),
            deny_permissions=props.get("deny_permissions", []),
            supports_multiple_selection=props.get("supports_multiple_selection", False),
            app_name=app_name,
            group=props.get("group"),
            group_default=props.get("group_default"),
        )

        # If the action isn't coming from the launch app, do not even bother putting the engine_name
        # in the hash. This simplifies the filtering process.
        if "engine_name" in props:
            command_data["engine_name"] = props["engine_name"]
        # If the launch app supported the software_entity_id property, we should save it in the
        # command's data as well so we can use it to do proper filtering of actions.
        if "software_entity_id" in props:
            command_data["software_entity_id"] = props["software_entity_id"]

        commands.append(command_data)

    engine.log_debug("Engine commands processed.")

    with open(output_file, "wt") as f:
        json.dump(commands, f)

    # Tear down the engine. This is both good practice before we exit
    # this process, but also necessary if there are multiple pipeline
    # configs that we're iterating over.
    engine.log_debug("Shutting down engine...")
    engine.destroy()


if __name__ == "__main__":
    arg_data_file = sys.argv[1]

    with open(arg_data_file, "rt") as fh:
        arg_data = json.load(fh)

    # The RPC api has given us the path to its tk-core to prepend
    # to our sys.path prior to importing sgtk. We'll prepend the
    # the path, import sgtk, and then clean up after ourselves.
    original_sys_path = copy.copy(sys.path)
    try:
        sys.path = [arg_data["sys_path"]] + sys.path
        import sgtk
    finally:
        sys.path = original_sys_path

    # Now that we have sgtk.util loaded, use it to make sure we have only utf-8 data in the args
    arg_data = sgtk.util.unicode.ensure_contains_str(arg_data)

    cache(
        arg_data["cache_file"],
        arg_data["output_file"],
        arg_data["data"],
        arg_data["base_configuration"],
        arg_data["engine_name"],
        arg_data["config_data"],
        arg_data["config_is_mutable"],
        arg_data["bundle_cache_fallback_paths"],
        sgtk.authentication.deserialize_user(arg_data["user"]),
    )

    sys.exit(0)

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
import cPickle
import os
import logging

# Special, non-engine commands that we'll need to handle ourselves.
CORE_INFO_COMMAND = "__core_info"
UPGRADE_CHECK_COMMAND = "__upgrade_check"

# We can't have a global logger instance, because we can't import sgtk
# in the global scope, but we can go ahead and define the logger name
# to be used throughout the script.
LOGGER_NAME = "wss2.execute_command"

def app_upgrade_info(engine):
    """
    Logs a message for the user that tells them how to check for app updates.
    This is provided for legacy purposes for "classic" SGTK setups.

    :param engine: The currently-running engine instance.
    """
    import sgtk
    logger = sgtk.LogManager.get_logger(LOGGER_NAME)

    code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

    logger.info(
        "In order to check if your installed apps and engines are up to date, "
        "you can run the following command in a console:"
    )

    logger.info("")
    config_root = engine.sgtk.pipeline_configuration.get_path()

    if sys.platform == "win32":
        tank_cmd = os.path.join(config_root, "tank.bat")
    else:
        tank_cmd = os.path.join(config_root, "tank")

    logger.info("<code style='%s'>%s updates</code>" % (code_css_block, tank_cmd))
    logger.info("")

def core_info(engine):
    """
    Builds and logs a report on whether the currently-installed core is up to
    data with what's in the app_store.

    :param engine: The currently-running engine instance.
    """
    import sgtk
    from sgtk.commands.core_upgrade import TankCoreUpdater
    logger = sgtk.LogManager.get_logger(LOGGER_NAME)

    code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

    # Create an upgrader instance that we can query if the install is up to date.
    installer = TankCoreUpdater(
        engine.sgtk.pipeline_configuration.get_install_location(),
        logger,
    )

    cv = installer.get_current_version_number()
    lv = installer.get_update_version_number()

    logger.info(
        "You are currently running version %s of the Shotgun Pipeline Toolkit." % cv
    )

    if not engine.sgtk.pipeline_configuration.is_localized():
        logger.info("")
        logger.info(
            "Your core API is located in <code>%s</code> and is shared with other "
            "projects." % install_root
        )

    logger.info("")
    status = installer.get_update_status()

    if status == TankCoreUpdater.UP_TO_DATE:
        logger.info(
            "<b>You are up to date! There is no need to update the Toolkit "
            "Core API at this time!</b>"
        )
    elif status == TankCoreUpdater.UPDATE_BLOCKED_BY_SG:
        req_sg = installer.get_required_sg_version_for_update()
        logger.warning(
            "<b>A new version (%s) of the core API is available however "
            "it requires a more recent version (%s) of Shotgun!</b>" % (lv, req_sg)
        )
    elif status == TankCoreUpdater.UPDATE_POSSIBLE:
        (summary, url) = installer.get_release_notes()

        logger.info("<b>A new version of the Toolkit API (%s) is available!</b>" % lv)
        logger.info("")
        logger.info(
            "<b>Change Summary:</b> %s <a href='%s' target=_new>"
            "Click for detailed Release Notes</a>" % (summary, url)
        )
        logger.info("")
        logger.info("In order to upgrade, execute the following command in a shell:")
        logger.info("")

        if sys.platform == "win32":
            tank_cmd = os.path.join(install_root, "tank.bat")
        else:
            tank_cmd = os.path.join(install_root, "tank")

        logger.info("<code style='%s'>%s core</code>" % (code_css_block, tank_cmd))
        logger.info("")
    else:
        raise sgtk.TankError("Unknown Upgrade state!")

def bootstrap(config, base_configuration, entity, engine_name):
    """
    Executes an engine command in the desired environment.

    :param dict config: The pipeline configuration entity.
    :param dict entity: The entity to give to the bootstrap manager when
        bootstrapping the engine.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"

    :returns: The bootstrapped engine instance.
    """
    # The local import of sgtk ensures that it occurs after sys.path is set
    # to what the server sent over.
    import sgtk
    logger = sgtk.LogManager.get_logger(LOGGER_NAME)

    # Setup the bootstrap manager.
    logger.debug("Preparing ToolkitManager for bootstrap.")
    manager = sgtk.bootstrap.ToolkitManager()

    # Not allowing config resolution to be overridden by environment
    # variables. This is here mostly for dev environment purposes, as
    # we'll use the env var to point to a dev config, but we don't
    # want that to then override everything else, like PipelineConfiguration
    # entities associated with the project.
    manager.allow_config_overrides = False
    manager.plugin_id = "basic.shotgun"
    manager.base_configuration = base_configuration

    if config:
        manager.pipeline_configuration = config.get("id")

    engine = manager.bootstrap_engine(engine_name, entity=entity)
    logger.debug("Engine %s started using entity %s" % (engine, entity))

    return engine

def execute(config, project, name, entities, base_configuration, engine_name):
    """
    Executes an engine command in the desired environment.

    :param dict config: The pipeline configuration entity.
    :param dict project: The project entity.
    :param str name: The name of the engine command to execute.
    :param list entities: The list of entities selected in the web UI when the
        command action was triggered.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"
    """
    # We need a single, representative entity when we bootstrap. The fact that
    # we might have gotten multiple entities from the client due to a
    # multiselection is only relevant later on when we're actually executing
    # the engine command. As such, pull the first entity off of the list.
    if entities:
        entity = entities[0]
    else:
        entity = project

    engine = bootstrap(config, base_configuration, entity, engine_name)

    import sgtk
    logger = sgtk.LogManager.get_logger(LOGGER_NAME)

    # Handle the "special" commands that aren't tied to any registered engine
    # commands.
    if name == CORE_INFO_COMMAND:
        core_info(engine)
        sys.exit(0)
    elif name == UPGRADE_CHECK_COMMAND:
        app_upgrade_info(engine)
        sys.exit(0)

    # Import sgtk here after the bootstrap. That will ensure that we get the
    # core that was swapped in during the bootstrap.
    import sgtk

    # We need to make sure that sgtk is accessible to any process that the
    # command execution spawns. We'll look up the path to the pipeline
    # config's install location and set PYTHONPATH such that core is
    # importable.
    core_root = os.path.join(
        engine.sgtk.pipeline_configuration.get_install_location(),
        "install",
        "core",
        "python"
    )
    sgtk.util.prepend_path_to_env_var(
        "PYTHONPATH",
        core_root,
    )

    command = engine.commands.get(name)

    if not command:
        msg = "Unable to find engine command: %s" % name
        logger.error(msg)
        raise sgtk.TankError(msg)

    # We need to know whether this command is allowed to be run when multiple
    # entities are selected. We can look for the special flag in the command's
    # properties to know whether that's the case.
    ms_flag = sgtk.platform.constants.LEGACY_MULTI_SELECT_ACTION_FLAG
    props = command["properties"]
    old_style = ms_flag in props

    if old_style:
        entity_ids = [e["id"] for e in entities]
        entity_type = entity["type"]
        engine.execute_old_style_command(name, entity_type, entity_ids)
    else:
        engine.execute_command(name)

if __name__ == "__main__":
    arg_data_file = sys.argv[1]

    with open(arg_data_file, "rb") as fh:
        arg_data = cPickle.load(fh)

    sys.path = arg_data["sys_path"]

    execute(
        arg_data["config"],
        arg_data["project"],
        arg_data["name"],
        arg_data["entities"],
        arg_data["base_configuration"],
        arg_data["engine_name"],
    )

    sys.exit(0)


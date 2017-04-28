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

def execute(config, project, name, entities, base_configuration, engine_name):
    """
    Executes an engine command in the desired environment.

    :param dict config: The pipeline configuration entity.
    :param dict project: The project entity.
    :param list entities: The list of entities selected in the web UI when the
        command action was triggered.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"
    """
    # The local import of sgtk ensures that it occurs after sys.path is set
    # to what the server sent over.
    import sgtk

    # Setup the bootstrap manager.
    toolkit_mgr = sgtk.bootstrap.ToolkitManager()
    toolkit_mgr.allow_config_overrides = False
    toolkit_mgr.plugin_id = "basic.shotgun"
    toolkit_mgr.base_configuration = base_configuration

    if config:
        toolkit_mgr.pipeline_configuration = config.get("id")

    # We need a single, representative entity when we bootstrap. The fact that
    # we might have gotten multiple entities from the client due to a
    # multiselection is only relevant later on when we're actually executing
    # the engine command. As such, pull the first entity off of the list.
    if entities:
        entity = entities[0]
    else:
        entity = project

    engine = toolkit_mgr.bootstrap_engine(engine_name, entity=entity)

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
        engine.logger.error(msg)
        raise RuntimeError(msg)

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


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
    import sgtk

    ms_flag = sgtk.platform.constants.LEGACY_MULTI_SELECT_ACTION_FLAG

    # Setup the bootstrap manager.
    toolkit_mgr = sgtk.bootstrap.ToolkitManager()
    toolkit_mgr.plugin_id = "basic.shotgun.execute"
    toolkit_mgr.base_configuration = base_configuration

    if config:
        toolkit_mgr.pipeline_configuration = config.get("id")

    if entities:
        entity = entities[0]
    else:
        entity = project

    engine = toolkit_mgr.bootstrap_engine(engine_name, entity=entity)
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

    with open(arg_data_file, "r") as fh:
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


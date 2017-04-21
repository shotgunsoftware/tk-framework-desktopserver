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
import glob
import os

def cache(cache_file, data, base_configuration, hash_data, engine_name):
    import sqlite3
    import sgtk

    entity = dict(type=data["entity_type"], id=data["entity_id"])
    project_entity = dict(id=data["project_id"], type="Project")

    # Setup the bootstrap manager.
    toolkit_mgr = sgtk.bootstrap.ToolkitManager(allow_config_overrides=False)
    toolkit_mgr.plugin_id = "basic.shotgun"
    toolkit_mgr.base_configuration = base_configuration

    pcs = toolkit_mgr.get_pipeline_configurations(
        project=project_entity,
    ) or [dict(id=None)]

    for pc in pcs:
        lookup_hash = hash_data[pc["id"]]["lookup_hash"]
        contents_hash = hash_data[pc["id"]]["contents_hash"]

        toolkit_mgr.pipeline_configuration = pc["id"]
        pc_descriptor = toolkit_mgr.resolve_descriptor(project_entity)
        engine = toolkit_mgr.bootstrap_engine(engine_name, entity=entity)

        engine.logger.debug("Engine %s started using entity %s" % (engine, entity))
        engine.logger.debug("Config descriptor: %s" % pc_descriptor)
        engine.logger.debug("Processing engine commands...")

        commands = []

        for cmd_name, data in engine.commands.iteritems():
            engine.logger.debug("Processing command: %s" % cmd_name)
            props = data["properties"]
            app = props.get("app")

            if app:
                app_name = app.name
            else:
                app_name = None

            commands.append(
                dict(
                    name=cmd_name,
                    title=props.get("title", cmd_name),
                    deny_permissions=props.get("deny_permissions", []),
                    supports_multiple_selection=props.get(
                        "supports_multiple_selection",
                        False
                    ),
                    app_name=app_name,
                    group=props.get("group"),
                    group_default=props.get("group_default"),
                    engine_name=props.get("engine_name"),
                ),
            )

        engine.logger.debug("Engine commands processed.")
        engine.logger.debug("Inserting commands into cache...")

        # Connect to the database and get the hashes we need to include in
        # the insert. Each of the lookups call out to the browser_integration
        # core hook.
        with sqlite3.connect(cache_file) as connection:
            connection.text_factory = str
            cursor = connection.cursor()

            commands_blob = sqlite3.Binary(
                cPickle.dumps(commands, cPickle.HIGHEST_PROTOCOL)
            )

            # Since we're likely to be updating out-of-date cached data more
            # often than we're going to be inserting new rows into the cache,
            # we'll try an update first. If no rows were affected by the update,
            # we move on to an insert.
            cursor.execute(
                "UPDATE engine_commands SET contents_hash=?, commands=? WHERE lookup_hash=?",
                (contents_hash, commands_blob, lookup_hash)
            )

            if cursor.rowcount == 0:
                engine.logger.debug(
                    "Update did not result in any rows altered, inserting..."
                )
                cursor.execute(
                    "INSERT INTO engine_commands VALUES (?, ?, ?)", (
                        lookup_hash,
                        contents_hash,
                        commands_blob,
                    )
                )

        # Tear down the engine. This is both good practice before we exit
        # this process, but also necessary if there are multiple pipeline
        # configs that we're iterating over.
        engine.logger.debug("Shutting down engine...")
        engine.destroy()

if __name__ == "__main__":
    arg_data_file = sys.argv[1]

    with open(arg_data_file, "rb") as fh:
        arg_data = cPickle.load(fh)

    sys.path = arg_data["sys_path"]

    cache(
        arg_data["cache_file"],
        arg_data["data"],
        arg_data["base_configuration"],
        arg_data["hash_data"],
        arg_data["engine_name"],
    )

    sys.exit(0)
    
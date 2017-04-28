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
import sqlite3
import contextlib

def cache(cache_file, data, base_configuration, engine_name, config_data):
    """
    Populates the sqlite cache with a row representing the desired pipeline
    configuration and entity type. If an entry already exists, it is updated.

    :param str cache_file: The path to the sqlite cache file on disk.
    :param dict data: The raw payload send down by the client.
    :param str base_configuration: The desired base pipeline configuration's
        uri.
    :param str engine_name: The name of the engine to bootstrap into. This
        is most likely going to be "tk-shotgun"
    :param dict config_data: All relevant pipeline configuration data. This
        dict is keyed by pipeline config entity id, each containing a dict
        that contains, at a minimum, "entity", "lookup_hash", and
        "contents_hash" keys.
    """
    # The local import of sgtk ensures that it occurs after sys.path is set
    # to what the server sent over.
    import sgtk

    entity = dict(type=data["entity_type"], id=data["entity_id"])
    project_entity = dict(id=data["project_id"], type="Project")

    # Setup the bootstrap manager.
    toolkit_mgr = sgtk.bootstrap.ToolkitManager()
    toolkit_mgr.allow_config_overrides = False
    toolkit_mgr.plugin_id = "basic.shotgun"
    toolkit_mgr.base_configuration = base_configuration

    for pc_id, pc_data in config_data.iteritems():
        pc = pc_data["entity"]
        lookup_hash = pc_data["lookup_hash"]
        contents_hash = pc_data["contents_hash"]

        toolkit_mgr.pipeline_configuration = pc_id
        engine = toolkit_mgr.bootstrap_engine(engine_name, entity=entity)

        engine.logger.debug("Engine %s started using entity %s" % (engine, entity))
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
            # This is to handle unicode properly - make sure that sqlite returns 
            # str objects for TEXT fields rather than unicode. Note that any unicode
            # objects that are passed into the database will be automatically
            # converted to UTF-8 strs, so this text_factory guarantees that any character
            # representation will work for any language, as long as data is either input
            # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
            # will always be unicode.
            connection.text_factory = str
            cursor = connection.cursor()

            # First, let's make sure that the database is actually setup with
            # the table we're expecting. If it isn't, then we can do that here.
            with contextlib.closing(connection.cursor()) as c:
                # Get a list of tables in the current database.
                ret = c.execute("SELECT name FROM main.sqlite_master WHERE type='table';")
                table_names = [x[0] for x in ret.fetchall()]

                if not table_names:
                    engine.logger.debug("Creating schema in sqlite db.")

                    # We have a brand new database. Create all tables and indices.
                    cursor.executescript("""
                        CREATE TABLE engine_commands (lookup_hash text, contents_hash text, commands blob);
                    """)

                    connection.commit()

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
        arg_data["engine_name"],
        arg_data["config_data"],
    )

    sys.exit(0)
    
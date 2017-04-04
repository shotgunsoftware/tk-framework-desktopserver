
import sys
import logging
import cPickle

class _BootstrapLogHandler(logging.StreamHandler):
    """
    Manually flushes emitted records for js to pickup.
    """

    def emit(self, record):
        """
        Forwards the record back to to js via the engine communicator.

        :param record: The record to log.
        """
        super(_BootstrapLogHandler, self).emit(record)

        # always flush to ensure its seen by the js process
        self.flush()

def get_sgtk_logger(sgtk):
    """
    Sets up a log handler and logger.

    :param sgtk: An sgtk module reference.

    :returns: A logger and log handler.
    """
    # add a custom handler to the root logger so that all toolkit log messages
    # are forwarded back to python via the communicator
    bootstrap_log_formatter = logging.Formatter("[%(levelname)s]: %(message)s")
    bootstrap_log_handler = _BootstrapLogHandler()
    bootstrap_log_handler.setFormatter(bootstrap_log_formatter)
    bootstrap_log_handler.setLevel(logging.DEBUG)

    # now get a logger to use during bootstrap
    sgtk_logger = sgtk.LogManager.get_logger("%s.%s" % ("tk-shotgun", "bootstrap"))
    sgtk.LogManager().initialize_custom_handler(bootstrap_log_handler)

    # allows for debugging to be turned on by the plugin build process
    sgtk.LogManager().global_debug = True

    # initializes the file where logging output will go
    sgtk.LogManager().initialize_base_file_handler("tk-shotgun")
    sgtk_logger.debug("Log dir: %s" % (sgtk.LogManager().log_folder))

    return sgtk_logger, bootstrap_log_handler

def get_contents_hash(tk, pc_descriptor):
    return tk.execute_core_hook_method(
        "browser_integration",
        "get_cache_contents_hash",
        pc_descriptor=pc_descriptor,
    )

def get_lookup_hash(tk, entity_type, pc_descriptor):
    return tk.execute_core_hook_method(
        "browser_integration",
        "get_cache_lookup_hash",
        entity_type=entity_type,
        pc_descriptor=pc_descriptor,
    )

def cache(cache_file, data):
    import sqlite3
    import sgtk

    entity = dict(type=data["entity_type"], id=data["entity_id"])
    project_entity = dict(id=data["project_id"], type="Project")

    # Setup the bootstrap manager.
    toolkit_mgr = sgtk.bootstrap.ToolkitManager()
    toolkit_mgr.plugin_id = "shotgun_toolkit_menu_caching"

    # toolkit_mgr.base_configuration = "sgtk:descriptor:app_store?name=tk-config-basic"
    toolkit_mgr.base_configuration = "sgtk:descriptor:dev?name=tk-config-basic&path=/Users/jeff/Documents/repositories/tk-config-basic"

    for pc in data["pipeline_configs"]:
        pc["project"] = pc.get("project", project_entity)

    pcs = toolkit_mgr.get_pipeline_configurations(
        project_entity,
        data["pipeline_configs"],
    ) or [dict(id=None)]

    for pc in pcs:
        logger, log_handler = get_sgtk_logger(sgtk)

        toolkit_mgr.pipeline_configuration = pc["id"]
        engine = toolkit_mgr.bootstrap_engine("tk-shotgun", entity=entity)
        pc_descriptor = toolkit_mgr.resolve_descriptor(project_entity)

        # Clean up the pre-bootstrap logger since we can use the engine's
        # logger from here on out.
        sgtk.LogManager().root_logger.removeHandler(log_handler)
        engine.logger.debug("Processing engine commands...")
        commands = []

        for cmd_name, data in engine.commands.iteritems():
            engine.logger.debug("Processing command: %s" % cmd_name)
            props = data["properties"]
            commands.append(
                dict(
                    name=cmd_name,
                    title=props.get("title", cmd_name),
                    deny_permissions=[], # TODO: figure out user permissions.
                    supports_multiple_selection=False, # TODO: figure out multiselect.
                ),
            )

        engine.logger.debug("Engine commands processed.")
        engine.logger.debug("Inserting commands into cache...")

        # Connect to the database and get the hashes we need to include in
        # the insert. Each of the lookups call out to the browser_integration
        # core hook.
        connection = sqlite3.connect(cache_file)
        connection.text_factory = str
        cursor = connection.cursor()

        try:
            lookup_hash = get_lookup_hash(
                engine.sgtk,
                entity["type"],
                pc_descriptor,
            )
            contents_hash = get_contents_hash(
                engine.sgtk,
                pc_descriptor,
            )
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
            connection.commit()
        finally:
            connection.close()

        # Tear down the engine. This is both good practice before we exit
        # this process, but also necessary if there are multiple pipeline
        # configs that we're iterating over.
        logger.debug("Shutting down engine...")
        engine.destroy()
        logger.debug("Engine shutdown complete.")

if __name__ == "__main__":
    arg_data_file = sys.argv[1]

    with open(arg_data_file, "r") as fh:
        arg_data = cPickle.load(fh)

    sys.path = arg_data["sys_path"]

    cache(
        arg_data["cache_file"],
        arg_data["data"],
    )

    sys.exit(0)
    

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

def get_lookup_hash(sgtk, engine, entity):
    pc = engine.sgtk.pipeline_configuration

def cache(cache_file, data):
    import sqlite3
    import sgtk

    entity = dict(type=data["entity_type"], id=data["entity_id"])

    # set up the toolkit boostrap manager
    toolkit_mgr = sgtk.bootstrap.ToolkitManager()
    toolkit_mgr.plugin_id = "shotgun_toolkit_menu_caching"
    # toolkit_mgr.base_configuration = "sgtk:descriptor:app_store?name=tk-config-basic"
    toolkit_mgr.base_configuration = "sgtk:descriptor:dev?name=tk-config-basic&path=/Users/jeff/Documents/repositories/tk-config-basic"

    for pc in data["pipeline_configs"]:
        pc["project"] = pc.get("project", dict(type="Project", id=data["project_id"]))

    pcs = toolkit_mgr.get_pipeline_configurations(
        project=dict(id=data["project_id"], type="Project"),
        pc_entities=data["pipeline_configs"],
    )

    for pc in pcs:
        logger, log_handler = get_sgtk_logger(sgtk)
        logger.info("Bootstrap logger up and running.")
        logger.info("Bootstrapping pipeline configuration [id=%s]..." % pc["id"])

        toolkit_mgr.pipeline_configuration = pc["id"]
        engine = toolkit_mgr.bootstrap_engine("tk-shotgun", entity=entity)
        pc_descriptor = toolkit_mgr.get_pipeline_configuration_descriptor(data["project_id"])

        logger.info("Bootstrap complete!")
        logger.info("PC descriptor: %s" % pc_descriptor.get_uri())

        sgtk.LogManager().root_logger.removeHandler(log_handler)
        engine.logger.info("Removed bootstrap log handler from root logger.")

        commands = []

        engine.logger.info("Processing engine commands...")

        for cmd_name, data in engine.commands.iteritems():
            engine.logger.info("Processing command: %s" % cmd_name)
            props = data["properties"]
            commands.append(
                dict(
                    name=cmd_name,
                    title=props.get("title", cmd_name),
                    deny_permissions=[], # TODO: figure out user permissions.
                    supports_multiple_selection=False, # TODO: figure out multiselect.
                ),
            )

        engine.logger.info("Engine commands processed.")
        engine.logger.info("Inserting into cache...")

        connection = sqlite3.connect(cache_file)
        connection.text_factory = str
        cursor = connection.cursor()

        lookup_hash = get_lookup_hash(sgtk, engine, entity)
        contents_hash = get_contents_hash(sgtk, engine, entity)

        try:
            cursor.execute(
                "INSERT INTO engine_commands VALUES (?, ?, ?)", (
                    lookup_hash,
                    contents_hash,
                    sqlite3.Binary(cPickle.dumps(commands, cPickle.HIGHEST_PROTOCOL)),
                )
            )
            connection.commit()
        finally:
            connection.close()

        logger.debug("Shutting down engine...")
        engine.destroy()
        logger.debug("Engine shutdown complete.")
    logger.info("Caching complete!")

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
    
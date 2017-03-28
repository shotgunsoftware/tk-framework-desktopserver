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
import md5
import sqlite3
import json
import subprocess
import tempfile

import sgtk

###########################################################################
# Decorators

def _db_connect(function):
    """
    Decorator helper to use with database methods. This is to reduce
    code duplication and it passes in a connection and cursor argument
    to the decorated method. Use it like this:
    
        @_db_connect
        def my_method(self, connection, cursor, note_id):
            do_stuff
        
    The connection and cursor parameters above are added by this decorator,
    so the calling code should execute the following:
    
        do_stuff
        self.my_method(note_id)
        do_stuff
    
    """
    def wrap_function(*args, **kwargs):
        connection = None
        cursor = None        
        self = args[0]
        try:
            connection = self._init_db()
            cursor = connection.cursor()
            new_args = (self, connection, cursor) + args[1:]
            return function(*new_args, **kwargs)
        finally:
            try:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
            except:
                self.logger.debug("Could not close database handle.")        
                    
    return wrap_function

###########################################################################
# Classes

class ShotgunAPI(object):
    """
    Public API
    Callable methods from client. Every one of these methods can be called from the client.
    """
    PUBLIC_API_METHODS = [
        "get_actions",
    ]

    DATABASE_FORMAT_VERSION = 1

    def __init__(self, host, process_manager):
        """
        API Constructor.
        Keep initialization pretty fast as it is created on every message.

        :param host: Host interface to communicate with. Abstracts the client.
        :param process_manager: Process Manager to use to interact with os processes.
        """
        self._host = host
        self._process_manager = process_manager
        self._engine = sgtk.platform.current_engine()

        # Cache path on disk.
        self._cache_path = os.path.join(
            self._engine.cache_location, 
            "shotgun_engine_commands_v%s.sqlite" % self.DATABASE_FORMAT_VERSION,
        )

    ###########################################################################
    # Properties

    @property
    def logger(self):
        return sgtk.platform.current_engine().logger

    @property
    def host(self):
        return self._host

    @property
    def process_manager(self):
        return self._process_manager

    ###########################################################################
    # Public methods

    @_db_connect
    def get_actions(self, connection, cursor, data):
        # TODO: Core hook to generate lookup hash.
        lookup_md5 = md5.new()
        lookup_md5.update(str(data))
        lookup_hash = lookup_md5.digest()

        # TODO: Compute contents_hash and ensure it matches that in the cache.
        res = list(cursor.execute(
            "SELECT commands FROM engine_commands WHERE lookup_hash=?",
            (lookup_hash,)
        ))

        if res:
            commands = cPickle.loads(str(list(res)[0][0]))
            self.logger.debug("Commands found in cache: %s" % commands)
            ret = dict(
                err="",
                retcode=0,
                out=commands,
            )
            self.host.reply(ret)
        else:
            # TODO: Second lookup_hash here to be replaced with contents_hash.
            self._cache_actions(data, lookup_hash, lookup_hash)
            self.get_actions(data)

    ###########################################################################
    # sqlite database access methods

    def _cache_actions(self, data, lookup_hash, contents_hash):
        self.logger.info("Caching engine commands...")

        script = os.path.join(
            os.path.dirname(__file__),
            "scripts",
            "cache_commands.py"
        )

        self.logger.debug("Executing script: %s" % script)
        args_file = tempfile.mkstemp()[1]

        with open(args_file, "w") as fh:
            cPickle.dump(
                dict(
                    cache_file=self._cache_path,
                    data=data,
                    lookup_hash=lookup_hash,
                    contents_hash=contents_hash,
                ),
                fh,
                cPickle.HIGHEST_PROTOCOL,
            )

        subprocess.check_call([sys.executable, script, args_file])
        self.logger.info("Caching complete.")

    def _init_db(self):
        """
        Sets up the database if it doesn't exist.

        :returns: A handle that must be closed.
        """
        connection = sqlite3.connect(self._cache_path)
        self.logger.info("Cache path is %s" % self._cache_path)

        # This is to handle unicode properly - make sure that sqlite returns 
        # str objects for TEXT fields rather than unicode. Note that any unicode
        # objects that are passed into the database will be automatically
        # converted to UTF-8 strs, so this text_factory guarantees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        connection.text_factory = str
        c = connection.cursor()

        try:
            # Get a list of tables in the current database.
            ret = c.execute("SELECT name FROM main.sqlite_master WHERE type='table';")
            table_names = [x[0] for x in ret.fetchall()]

            if not table_names:
                self.logger.debug("Creating schema in sqlite db.")

                # We have a brand new database. Create all tables and indices.
                c.executescript("""
                    CREATE TABLE engine_commands (lookup_hash text, contents_hash text, commands blob);
                """)
                # c.executescript("""
                #     -- CREATE TABLE entity (entity_type text, entity_id integer, activity_id integer, created_at datetime);

                #     -- CREATE TABLE activity (activity_id integer, note_id integer default null, payload blob, created_at datetime);

                #     -- CREATE TABLE note (note_id integer, payload blob, created_at datetime);

                #     -- CREATE INDEX entity_1 ON entity(entity_type, entity_id, created_at);
                #     -- CREATE INDEX entity_2 ON entity(entity_type, entity_id, activity_id, created_at);

                #     -- CREATE INDEX activity_1 ON activity(activity_id);
                #     -- CREATE INDEX activity_2 ON activity(activity_id, note_id);

                #     -- CREATE INDEX note_1 ON activity(note_id);
                # """)
                connection.commit()
        except Exception:
            connection.close()
            c = None
            raise
        finally:
            if c:
                c.close()

        return connection









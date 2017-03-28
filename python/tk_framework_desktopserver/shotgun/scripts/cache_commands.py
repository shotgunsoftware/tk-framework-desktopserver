
import sys
import sqlite3
import cPickle

def cache(cache_file, data, lookup_hash, contents_hash):
    import sqlite3

    connection = sqlite3.connect(cache_file)
    connection.text_factory = str
    cursor = connection.cursor()

     # TODO: bootstrap and get commands
    try:
        commands = [dict(name="YYYYAAAAAAAYYYYY")]
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

if __name__ == "__main__":
    arg_data_file = sys.argv[1]

    with open(arg_data_file, "r") as fh:
        arg_data = cPickle.load(fh)

    cache(
        arg_data["cache_file"],
        arg_data["data"],
        arg_data["lookup_hash"],
        arg_data["contents_hash"],
    )

    sys.exit(0)
    
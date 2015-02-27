# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import subprocess
from threading  import Thread
from Queue import Queue, Empty


class Command(object):

    @staticmethod
    def _enqueue_output(out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

    @staticmethod
    def call_cmd(args):
        # Note: Tie stdin to a PIPE as well to avoid this python bug on windows
        # http://bugs.python.org/issue3905
        # Queue code taken from: http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
        try:
            process = subprocess.Popen(args,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.stdin.close()

            stdout_q = Queue()
            stdout_thread = Thread(target=Command._enqueue_output, args=(process.stdout, stdout_q))
            stdout_thread.daemon = True # thread dies with the program
            stdout_thread.start()

            stderr_q = Queue()
            stderr_thread = Thread(target=Command._enqueue_output, args=(process.stderr, stderr_q))
            stderr_thread.daemon = True # thread dies with the program
            stderr_thread.start()

            # Popen.communicate() doesn't play nicely if the stdin pipe is closed
            # as it tries to flush it causing an 'I/O error on closed file' error
            # when run from a terminal
            #
            # to avoid this, lets just poll the output from the process until
            # it's finished
            stdout_lines = []
            stderr_lines = []
            while stdout_thread.isAlive() and stderr_thread.isAlive():
                # read line without blocking
                try:
                    stdout_line = stdout_q.get_nowait()
                except Empty:
                    # no output yet
                    pass
                else:
                    # got line
                    stdout_lines.append(stdout_line)

                # read line without blocking
                try:
                    stderr_line = stderr_q.get_nowait()
                except Empty:
                    # no output yet
                    pass
                else:
                    # got line
                    stderr_lines.append(stderr_line)

            ret = process.poll()
        except StandardError:
            import traceback
            ret = True
            stderr_lines = traceback.format_exc().split()
            stderr_lines.append("%s" % args)

        return ret, '\n'.join(stdout_lines), '\n'.join(stderr_lines)

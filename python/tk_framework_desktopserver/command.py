# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import shutil
import subprocess
from threading import Thread
import tempfile
import sys
from queue import Queue
import traceback
from .logger import get_logger

import sgtk.util

logger = get_logger(__name__)

# Extensions of the scripts that Windows always runs through cmd.exe, even without
# shell=True.
_BATCH_EXTENSIONS = (".bat", ".cmd")

# Characters that cmd.exe still interprets inside a quoted argument, or that would
# end the quoted argument early. A batch file argument containing one of them could
# inject commands, so such arguments are rejected.
_UNSAFE_BATCH_CHARACTERS = frozenset('\x00\n\r"%!')


class ReadThread(Thread):
    """
    Thread that reads a pipe.
    """

    def __init__(self, p_out, target_queue):
        """
        Constructor.

        :param p_out: Pipe to read.
        :param target_queue: Queue that will accumulate the pipe output.
        """
        Thread.__init__(self, daemon=True)
        self.pipe = p_out
        self.target_queue = target_queue

    def run(self):
        """
        Reads the contents of the pipe and adds it to the queue until the pipe
        is closed.
        """
        while True:
            line = self.pipe.readline()  # blocking read
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if line == "":
                break
            self.target_queue.put(line)


class Command(object):
    @staticmethod
    def _create_temp_file():
        """
        :returns: Returns the path to a temporary file.
        """
        handle, path = tempfile.mkstemp(prefix="desktop_server")
        os.close(handle)
        return path

    @staticmethod
    def call_cmd(args):
        """
        Runs a command in a separate process.

        :param args: Command line tokens.

        :returns: A tuple containing (exit code, stdout, stderr).
        """
        # The commands that are being run are probably being launched from Desktop, which would
        # have a TANK_CURRENT_PC environment variable set to the site configuration. Since we
        # preserve that value for subprocesses (which is usually the behavior we want), the DCCs
        # being launched would try to run in the project environment and would get an error due
        # to the conflict.
        #
        # Clean up the environment to prevent that from happening.
        env = os.environ.copy()
        vars_to_remove = ["TANK_CURRENT_PC"]
        for var in vars_to_remove:
            if var in env:
                del env[var]

        # Launch the child process
        # Windows needs output redirected to files and batch files quoted for cmd.exe,
        # so we'll provide two implementations. See the Windows implementation for
        # more details.
        if sgtk.util.is_windows():
            ret, stdout_lines, stderr_lines = Command._call_cmd_win32(args, env)
        else:
            ret, stdout_lines, stderr_lines = Command._call_cmd_unix(args, env)

        out = "".join(stdout_lines)
        err = "".join(stderr_lines)

        return ret, out, err

    @staticmethod
    def _call_cmd_unix(args, env):
        """
        Runs a command in a separate process. Implementation for Unix based OSes.

        :param args: Command line tokens.
        :param env: Environment variables to set for the subprocess.

        :returns: A tuple containing (exit code, stdout, stderr).
        """
        # Note: Tie stdin to a PIPE as well to avoid this python bug on windows
        # http://bugs.python.org/issue3905
        # Queue code taken from: http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
        stdout_lines = []
        stderr_lines = []

        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            process.stdin.close()

            stdout_q = Queue()
            stderr_q = Queue()

            stdout_t = ReadThread(process.stdout, stdout_q)
            stdout_t.start()

            stderr_t = ReadThread(process.stderr, stderr_q)
            stderr_t.start()

            # Popen.communicate() doesn't play nicely if the stdin pipe is closed
            # as it tries to flush it causing an 'I/O error on closed file' error
            # when run from a terminal
            #
            # to avoid this, lets just poll the output from the process until
            # it's finished
            process.wait()

            try:
                process.stdout.flush()
                process.stderr.flush()
            except IOError:
                # This fails on OSX 10.7, but it looks like there's no ill side effect
                # from failing on that platform so we can ignore it.
                logger.exception("Error while flushing file descriptor:")
            stdout_t.join()
            stderr_t.join()

            while not stdout_q.empty():
                stdout_lines.append(stdout_q.get())

            while not stderr_q.empty():
                stderr_lines.append(stderr_q.get())

            ret = process.returncode
        except Exception:
            # Do not log the command line, it might contain sensitive information!
            logger.exception("Error running subprocess:")

            ret = 1
            stderr_lines = traceback.format_exc().splitlines(True)
            stderr_lines.append("%s" % args)

        return ret, stdout_lines, stderr_lines

    @staticmethod
    def _build_batch_command_line(args):
        """
        Builds a cmd.exe command line that runs a batch file with the given arguments.

        Every argument is quoted, and arguments containing characters that cmd.exe
        would still interpret inside quotes are rejected, so no argument can inject
        commands.

        :param args: Command line tokens. The first one is the batch file.

        :returns: The command line to pass to cmd.exe /s /c.

        :raises ValueError: If an argument cannot be passed safely to a batch file.
        """
        quoted_args = []
        for arg in args:
            if not isinstance(arg, str):
                raise ValueError(
                    "Batch file arguments must be strings, got %s." % type(arg).__name__
                )
            if _UNSAFE_BATCH_CHARACTERS.intersection(arg):
                raise ValueError(
                    "A batch file argument contains a character that cannot be passed "
                    'safely: ", %, !, a newline or a null character.'
                )
            # The batch file usually hands its arguments on to a program that treats
            # backslashes before a quote as escapes, so double the trailing ones.
            trailing_backslashes = len(arg) - len(arg.rstrip("\\"))
            quoted_args.append('"%s%s"' % (arg, "\\" * trailing_backslashes))

        # With /s, cmd.exe removes the outer quotes and runs the rest as it is.
        return '"%s"' % " ".join(quoted_args)

    @staticmethod
    def _call_cmd_win32(args, env):
        """
        Runs a command in a separate process. Implementation for Windows.

        The command is never run through a shell. Batch files, which Windows can only
        run through cmd.exe, are run with every argument quoted and validated by
        :meth:`_build_batch_command_line`.

        :param args: Command line tokens.
        :param env: Environment variables to set for the subprocess.

        :returns: A tuple containing (exit code, stdout, stderr).
        """
        stdout_lines = []
        stderr_lines = []
        stdout_path = None
        stderr_path = None
        try:
            # On Windows, file descriptors like sockets can be inherited by child
            # process and are only closed when the main process and all child
            # processes are closed. This is bad because it means that the port
            # the websocket server uses will never be released as long as any DCCs
            # or tank commands are running. Therefore, closing the Desktop and
            # restarting it for example wouldn't free the port and would give the
            # "port 9000 already in use" error we've seen before.
            #
            # To avoid this, close_fds needs to be specified when launching a child
            # process. Since Python 3.7, close_fds can be combined with redirected
            # standard handles on Windows: only those handles are inherited. The
            # output is redirected to two temporary files rather than pipes, which
            # are read when the child process is over.
            #
            # A batch file can only run through cmd.exe, which parses the whole
            # command line, so it is run explicitly with strictly quoted arguments.
            # Anything else is run directly, with no shell. shutil.which resolves a
            # name without an extension the way the shell used to, through PATHEXT.
            executable = shutil.which(args[0]) or args[0]
            extension = os.path.splitext(executable.rstrip(" ."))[1].lower()
            if extension in _BATCH_EXTENSIONS:
                cmd_exe = os.path.join(
                    os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cmd.exe"
                )
                batch_command_line = Command._build_batch_command_line(
                    [executable] + list(args[1:])
                )
                popen_args = '"%s" /e:on /v:off /s /c %s' % (
                    cmd_exe,
                    batch_command_line,
                )
            else:
                cmd_exe = None
                popen_args = [executable] + list(args[1:])

            stdout_path = Command._create_temp_file()
            stderr_path = Command._create_temp_file()

            # Prevents a console window from appearing on Windows.
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            with open(stdout_path, "wb") as stdout_file, open(
                stderr_path, "wb"
            ) as stderr_file:
                process = subprocess.Popen(
                    popen_args,
                    close_fds=True,
                    env=env,
                    executable=cmd_exe,
                    startupinfo=startupinfo,
                    stderr=stderr_file,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                )
                process.wait()

            # Read back the output from the two. Decode as utf-8 with
            # errors="replace" rather than relying on the OS locale codec:
            # on non-utf-8 locales (e.g. cp932 on Japanese Windows) open()
            # would otherwise raise UnicodeDecodeError on non-ASCII output.
            with open(
                stdout_path, "rt", encoding="utf-8", errors="replace"
            ) as stdout_file:
                stdout_lines = [l for l in stdout_file]

            with open(
                stderr_path, "rt", encoding="utf-8", errors="replace"
            ) as stderr_file:
                stderr_lines = [l for l in stderr_file]

            # Track the result code.
            ret = process.returncode

        except Exception:
            logger.exception("Error running subprocess:")

            ret = 1
            stderr_lines = traceback.format_exc().splitlines(True)
            stderr_lines.append("%s" % args)

        # Don't lose any sleep over temporary files that can't be deleted.
        for temp_path in (stdout_path, stderr_path):
            if temp_path is None:
                continue
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return ret, stdout_lines, stderr_lines

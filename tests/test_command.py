# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import sgtk

# The framework package imports Qt at import time; mock it since Qt is not available
# under test (same approach as the other suites, e.g. tests/settings/test_settings.py).
sgtk.platform.qt.QtCore = Mock()
sgtk.platform.qt.QtGui = Mock()

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(repo_root, "python"))

from tk_framework_desktopserver.command import Command  # noqa: E402

# The defects fixed here (SG-44961) live in _call_cmd_win32, so these tests only
# make sense on Windows.
windows_only = unittest.skipUnless(
    sys.platform == "win32", "command._call_cmd_win32 is Windows-only"
)


@windows_only
class TestCallCmdWin32(unittest.TestCase):
    """
    Regression tests for SG-44961.

    Bug 1: the stdout/stderr temp files were read with the OS locale codec (cp932 on
    Japanese Windows), so non-ASCII subprocess output raised UnicodeDecodeError.
    Bug 2: the win32 exception handler wrapped the traceback list inside another list,
    so call_cmd's "".join(stderr_lines) raised
    "TypeError: sequence item 0: expected str instance, list found".
    """

    def _write_child(self, body):
        """Write a small child script to a temp .py file and return its path."""
        handle, path = tempfile.mkstemp(suffix=".py", prefix="sg44961_child_")
        os.close(handle)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_non_ascii_stderr_does_not_crash(self):
        """
        Bug 1: a child emitting bytes that are illegal under the OS locale codec must
        not crash the reader. The pair 0x81 0xff is undecodable under cp932, cp1252 and
        strict utf-8 alike, so on the pre-fix code open() raises UnicodeDecodeError
        regardless of the machine locale; with the fix, errors="replace" turns the bytes
        into U+FFFD and the call returns cleanly.
        """
        child = self._write_child(
            "import sys\n"
            "sys.stderr.buffer.write(b'engine bootstrap line\\n')\n"
            "sys.stderr.buffer.write(bytes([0x81, 0xff]))\n"
            "sys.stderr.buffer.write(b'\\ntrailing line\\n')\n"
            "sys.exit(3)\n"
        )

        ret, out, err = Command.call_cmd([sys.executable, child])

        self.assertEqual(ret, 3)
        self.assertIsInstance(err, str)
        self.assertIn("�", err)  # undecodable bytes replaced, not raised
        self.assertIn("engine bootstrap line", err)

    def test_exception_handler_returns_joinable_lines(self):
        """
        Bug 2: when the try block raises, the handler must leave stderr_lines as a flat
        list of strings so call_cmd's "".join(...) succeeds instead of raising TypeError.
        """
        with patch(
            "tk_framework_desktopserver.command.subprocess.Popen",
            side_effect=RuntimeError("boom"),
        ):
            ret, out, err = Command.call_cmd([sys.executable, "-c", "pass"])

        self.assertEqual(ret, 1)
        self.assertIsInstance(err, str)
        self.assertIn("Traceback", err)


class TestBuildBatchCommandLine(unittest.TestCase):
    """
    SG-47020: batch files always run through cmd.exe, and read their own arguments
    again, so arguments are quoted as shell=True always did and arguments containing
    a character that cmd.exe interprets are rejected.
    """

    def test_arguments_are_quoted_as_before(self):
        """
        Only arguments with spaces are quoted, as subprocess did with shell=True, so
        tank.bat's IF "%1"=="shotgun_get_actions" still matches.
        """
        line = Command._build_batch_command_line(
            [
                "C:\\cfg\\tank.bat",
                "shotgun_get_actions",
                "shotgun_windows_shot.txt",
                "with space",
                "123,456",
            ]
        )
        self.assertEqual(
            line,
            '""C:\\cfg\\tank.bat" shotgun_get_actions shotgun_windows_shot.txt '
            '"with space" 123,456"',
        )

    def test_batch_file_path_may_contain_parentheses(self):
        line = Command._build_batch_command_line(
            ["C:\\Program Files (x86)\\cfg\\tank.bat", "shotgun_run_action"]
        )
        self.assertEqual(
            line, '""C:\\Program Files (x86)\\cfg\\tank.bat" shotgun_run_action"'
        )

    def test_trailing_backslashes_are_doubled_when_quoted(self):
        line = Command._build_batch_command_line(["x.bat", "C:\\my dir\\"])
        self.assertEqual(line, '""x.bat" "C:\\my dir\\\\""')

    def test_unsafe_argument_characters_are_rejected(self):
        for arg in (
            'a"&calc',
            "%PATH%",
            "!x!",
            "a&calc",
            "a & calc",
            "a|calc",
            "a>file",
            "a<file",
            "a^b",
            "a(b",
            "a)b",
            "a\nb",
            "a\rb",
            "a\x00b",
        ):
            with self.subTest(arg=arg):
                with self.assertRaisesRegex(ValueError, "cannot be passed safely"):
                    Command._build_batch_command_line(["x.bat", arg])

    def test_unsafe_batch_file_path_characters_are_rejected(self):
        for path in ('C:\\a"b\\x.bat', "C:\\%TEMP%\\x.bat", "C:\\a!b\\x.bat"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "cannot be passed safely"):
                    Command._build_batch_command_line([path, "arg"])

    def test_non_string_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            Command._build_batch_command_line(["x.bat", 42])


@windows_only
class TestCallCmdWin32NoShell(unittest.TestCase):
    """
    SG-47020: commands run without shell=True, arguments reach executables
    literally, and arguments that a batch file could run as commands are rejected.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sg47020 dir ")
        self.addCleanup(self._remove_temp_dir)
        self.marker = os.path.join(self.temp_dir, "injected")

    def _remove_temp_dir(self):
        for name in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, name))
        os.rmdir(self.temp_dir)

    def _write_batch_file(self, name, lines):
        path = os.path.join(self.temp_dir, name)
        with open(path, "w") as f:
            f.write("\r\n".join(["@echo off", *lines, ""]))
        return path

    def _write_echo_batch_file(self):
        """
        Write a batch file that prints each argument with %~1, which removes the
        quotes, so any cmd.exe character in an argument would run.
        """
        return self._write_batch_file(
            "print args.bat",
            [
                ":loop",
                "if [%1]==[] goto end",
                "echo ARG=%~1",
                "shift",
                "goto loop",
                ":end",
            ],
        )

    def test_popen_is_called_without_shell(self):
        with patch(
            "tk_framework_desktopserver.command.subprocess.Popen",
            wraps=__import__("subprocess").Popen,
        ) as popen:
            ret, out, err = Command.call_cmd([sys.executable, "-c", "print('ok')"])

        self.assertEqual(ret, 0, err)
        self.assertIn("ok", out)
        self.assertFalse(popen.call_args.kwargs.get("shell", False))

    def test_executable_arguments_are_not_interpreted(self):
        ret, out, err = Command.call_cmd(
            [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1:])",
                f"a & echo x > {self.marker}",
            ]
        )
        self.assertEqual(ret, 0, err)
        self.assertIn("a & echo x > ", out)
        self.assertFalse(os.path.exists(self.marker))

    def test_batch_file_arguments_are_passed(self):
        batch_file = self._write_echo_batch_file()
        ret, out, err = Command.call_cmd(
            [batch_file, "shotgun_run_action", "with space", "Shot", "123,456"]
        )

        # cmd.exe splits %1 on commas, as it always has; tank.bat passes its
        # arguments on with %*, which keeps "123,456" whole.
        self.assertEqual(ret, 0, err)
        self.assertEqual(
            [line for line in out.splitlines() if line.startswith("ARG=")],
            [
                "ARG=shotgun_run_action",
                "ARG=with space",
                "ARG=Shot",
                "ARG=123",
                "ARG=456",
            ],
        )

    def test_tank_style_argument_comparison_still_matches(self):
        """
        tank.bat starts with IF "%1"=="shotgun_get_actions", which only matches if
        the argument is passed without quotes.
        """
        batch_file = self._write_batch_file(
            "tank.bat",
            [
                'IF "%1"=="shotgun_get_actions" GOTO CHECK_CACHE',
                "echo SLOW",
                "exit /b 0",
                ":CHECK_CACHE",
                "echo CACHE %2 %3",
                "exit /b 0",
            ],
        )
        ret, out, err = Command.call_cmd(
            [batch_file, "shotgun_get_actions", "cache.txt", "env.yml"]
        )

        self.assertEqual(ret, 0, err)
        self.assertIn("CACHE cache.txt env.yml", out)

    def test_batch_file_injection_is_rejected(self):
        batch_file = self._write_echo_batch_file()
        for arg in (
            f"a&echo x>{self.marker}",
            f"b|echo x>{self.marker}",
            f'"&echo x>"{self.marker}"&rem "',
            "%COMSPEC%",
        ):
            with self.subTest(arg=arg):
                ret, out, err = Command.call_cmd([batch_file, arg])

                self.assertEqual(ret, 1)
                self.assertIn("cannot be passed safely", err)
                self.assertFalse(os.path.exists(self.marker))


if __name__ == "__main__":
    unittest.main()

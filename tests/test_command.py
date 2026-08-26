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


if __name__ == "__main__":
    unittest.main()

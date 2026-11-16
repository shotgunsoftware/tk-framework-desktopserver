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

from tk_framework_desktopserver.process_manager import (  # noqa: E402
    BLOCKED_OPEN_EXTENSIONS,
    OpenFileRejectedError,
    ProcessManager,
)

PROCESS_MANAGER = "tk_framework_desktopserver.process_manager"


class TestVerifyFileOpen(unittest.TestCase):
    """
    SG-47020: the open command must refuse paths that would run code.
    """

    def setUp(self):
        self.manager = ProcessManager()
        self.temp_dir = tempfile.mkdtemp(prefix="sg47020_")
        self.addCleanup(self._remove_temp_dir)

    def _remove_temp_dir(self):
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                path = os.path.join(root, name)
                if os.path.islink(path):
                    os.remove(path)
                else:
                    os.rmdir(path)
        os.rmdir(self.temp_dir)

    def _create_file(self, name):
        path = os.path.join(self.temp_dir, name)
        with open(path, "w") as f:
            f.write("data")
        return path

    def test_blocked_extensions_are_rejected(self):
        """
        Every blocked extension is rejected, whatever its case, even when the file
        does not exist.
        """
        for extension in sorted(BLOCKED_OPEN_EXTENSIONS):
            for variant in (extension, extension.upper()):
                with self.subTest(extension=variant):
                    path = os.path.join(self.temp_dir, "file" + variant)
                    with self.assertRaises(OpenFileRejectedError):
                        self.manager._verify_file_open(path)

    def test_windows_trailing_dots_and_spaces_are_ignored(self):
        """
        Windows runs "file.exe." and "file.exe " as "file.exe".
        """
        for name in ("file.exe.", "file.exe ", "file.exe. .", "file.bat..."):
            with self.subTest(name=name):
                with self.assertRaises(OpenFileRejectedError):
                    self.manager._verify_file_open(os.path.join(self.temp_dir, name))

    def test_application_bundle_directory_is_rejected(self):
        """
        A macOS application bundle is a directory; opening it launches the app.
        """
        bundle = os.path.join(self.temp_dir, "Evil.app")
        os.mkdir(bundle)
        for path in (bundle, bundle + "/"):
            with self.subTest(path=path):
                with self.assertRaises(OpenFileRejectedError):
                    self.manager._verify_file_open(path)

    def test_ordinary_files_and_folders_are_accepted(self):
        """
        Files that only open in a viewer or an application, and folders, still open.
        """
        for name in ("shot.mov", "plate.0001.exr", "scene.ma", "notes.txt", "README"):
            with self.subTest(name=name):
                self.manager._verify_file_open(self._create_file(name))
        self.manager._verify_file_open(self.temp_dir)

    def test_missing_file_is_still_reported(self):
        with self.assertRaisesRegex(Exception, "Path not found"):
            self.manager._verify_file_open(os.path.join(self.temp_dir, "missing.mov"))

    def test_invalid_paths_are_rejected(self):
        for filepath in (None, "", 42, ["shot.mov"]):
            with self.subTest(filepath=filepath):
                with self.assertRaises(OpenFileRejectedError):
                    self.manager._verify_file_open(filepath)

    @unittest.skipIf(sys.platform == "win32", "Creating symlinks needs privileges")
    def test_symlink_to_blocked_file_is_rejected(self):
        """
        A link named like a movie must not open the program it points at.
        """
        target = self._create_file("payload.sh")
        link = os.path.join(self.temp_dir, "shot.mov")
        os.symlink(target, link)
        with self.assertRaisesRegex(OpenFileRejectedError, r"shot\.mov.*\.sh"):
            self.manager._verify_file_open(link)


@patch(PROCESS_MANAGER + ".sgtk.util.is_windows", return_value=True)
class TestVerifyWindowsPath(unittest.TestCase):
    """
    SG-47020: on Windows, the open command must refuse UNC paths outside the site's
    local storage roots, and alternate data streams.
    """

    def setUp(self):
        self.manager = ProcessManager()
        self.shotgun = Mock()
        self.shotgun.find.return_value = [
            {"type": "LocalStorage", "id": 1, "windows_path": "\\\\filer\\projects"},
            {"type": "LocalStorage", "id": 2, "windows_path": "P:\\"},
            {"type": "LocalStorage", "id": 3, "windows_path": None},
            {"type": "LocalStorage", "id": 4, "windows_path": "\\\\filer\\shows\\demo"},
        ]
        bundle_patcher = patch(
            PROCESS_MANAGER + ".sgtk.platform.current_bundle",
            return_value=Mock(shotgun=self.shotgun),
        )
        bundle_patcher.start()
        self.addCleanup(bundle_patcher.stop)

    def test_unc_paths_outside_storage_roots_are_rejected_before_access(
        self, is_windows
    ):
        """
        Even checking that a UNC path exists sends the user's credentials to the
        server, so the path is rejected before it is touched.
        """
        for filepath in (
            "\\\\attacker\\share\\shot.mov",
            "//attacker/share/shot.mov",
            "\\\\filer\\projects-other\\shot.mov",
            "\\\\filer\\shows\\demo\\..\\private\\shot.mov",
            "\\\\?\\UNC\\attacker\\share\\shot.mov",
            "\\\\.\\pipe\\shot.mov",
        ):
            with self.subTest(filepath=filepath):
                with patch(PROCESS_MANAGER + ".os.path.exists") as exists:
                    with self.assertRaisesRegex(OpenFileRejectedError, "network"):
                        self.manager._verify_file_open(filepath)
                    exists.assert_not_called()

    def test_unc_paths_inside_storage_roots_are_accepted(self, is_windows):
        for filepath in (
            "\\\\filer\\projects",
            "\\\\filer\\projects\\show\\shot.mov",
            "//FILER/Projects/show/shot.mov",
        ):
            with self.subTest(filepath=filepath):
                self.manager._verify_windows_path(filepath)

    def test_storage_roots_are_cached(self, is_windows):
        self.manager._verify_windows_path("\\\\filer\\projects\\a.mov")
        self.manager._verify_windows_path("\\\\filer\\projects\\b.mov")
        self.shotgun.find.assert_called_once_with("LocalStorage", [], ["windows_path"])

    def test_storage_lookup_failure_rejects_and_retries(self, is_windows):
        self.shotgun.find.side_effect = RuntimeError("offline")
        with self.assertRaises(OpenFileRejectedError):
            self.manager._verify_windows_path("\\\\filer\\projects\\a.mov")

        self.shotgun.find.side_effect = None
        self.manager._verify_windows_path("\\\\filer\\projects\\a.mov")
        self.assertEqual(self.shotgun.find.call_count, 2)

    def test_drive_paths_are_accepted(self, is_windows):
        for filepath in ("C:\\show\\shot.mov", "Z:/show/shot.mov", "relative\\a.mov"):
            with self.subTest(filepath=filepath):
                self.manager._verify_windows_path(filepath)
        self.shotgun.find.assert_not_called()

    def test_alternate_data_streams_are_rejected(self, is_windows):
        for filepath in (
            "C:\\show\\shot.mov:payload.exe",
            "C:\\show\\notes.txt:hidden",
            "shot.mov:payload",
            "\\\\filer\\projects\\shot.mov:payload",
        ):
            with self.subTest(filepath=filepath):
                with self.assertRaisesRegex(OpenFileRejectedError, "data stream"):
                    self.manager._verify_file_open(filepath)


if __name__ == "__main__":
    unittest.main()

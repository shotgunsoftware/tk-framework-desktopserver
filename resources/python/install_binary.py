# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""Cross-platform binary requirements installer.

Platform directory mapping:
  linux  -> bin/<version>/linux
  darwin -> bin/<version>/mac
  win32  -> bin/<version>/win

Usage: python install_binary.py
"""

import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile

from pip._internal.cli.main import main as pip_main

_PLATFORM_DIR = {
    "linux": "linux",
    "darwin": "mac",
    "win32": "win",
}

platform_dir = _PLATFORM_DIR[sys.platform]

python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
bin_dir = pathlib.Path("bin") / python_version / platform_dir
requirements = pathlib.Path("bin") / python_version / "explicit_requirements.txt"

# Delete and recreate the bin directory
shutil.rmtree(bin_dir, ignore_errors=True)
bin_dir.mkdir(parents=True)

# Build pip install arguments
pip_args = [
    "install",
    "--target",
    os.fspath(bin_dir),
    "--no-deps",
    "--requirement",
    os.fspath(requirements),
]

# Linux requires explicit manylinux platform tags so that pip downloads the
# correct pre-built wheels regardless of the host platform.
# See: https://deepwiki.com/pypa/manylinux#policy-and-platform-support-matrix
if sys.platform == "linux":
    pip_args += [
        "--platform",
        "manylinux_2_28_x86_64",
        "--platform",
        "manylinux2014_x86_64",
        "--platform",
        "manylinux2010_x86_64",
        "--prefer-binary",
    ]

if pip_main(pip_args) != 0:
    raise SystemExit("pip install failed")

# Python 3.10+ is bundled with SGD Universal builds (SGD 1.9+), which run
# natively on both Intel and Apple Silicon. Some packages (e.g. cffi,
# zope.interface) do not publish universal wheels on PyPI, so we
# cross-compile them for the opposite architecture using ARCHFLAGS and
# combine the results into universal binaries with lipo.
# This works on any macOS machine without needing a dedicated arm64 runner.
#
# Python 3.9 and below are bundled with older Intel-only SGD builds. On
# Apple Silicon those SGD versions run entirely under Rosetta 2, so
# x86_64-only .so files are correct - no universal binaries needed.
if sys.platform == "darwin" and sys.version_info.minor >= 10:
    native_arch = platform.machine()
    cross_arch = "x86_64" if native_arch == "arm64" else "arm64"
    print(f"Native arch: {native_arch} - cross-compiling for: {cross_arch}")

    with tempfile.TemporaryDirectory() as tmp_cross:
        env = os.environ.copy()
        env["ARCHFLAGS"] = f"-arch {cross_arch}"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                tmp_cross,
                "--no-deps",
                "--no-binary",
                "cffi",
                "--no-binary",
                "zope.interface",
                "--requirement",
                os.fspath(requirements),
            ],
            env=env,
        )
        if result.returncode != 0:
            raise SystemExit("Cross-arch pip install failed")

        tmp_cross_path = pathlib.Path(tmp_cross)
        for cross_so in tmp_cross_path.rglob("*.so"):
            rel_path = cross_so.relative_to(tmp_cross_path)
            native_so = bin_dir / rel_path
            if native_so.exists():
                file_output = subprocess.run(
                    ["file", str(native_so)],
                    capture_output=True,
                    text=True,
                ).stdout
                if "universal binary" not in file_output:
                    print(f"Creating universal binary: {rel_path}")
                    fat = native_so.with_suffix(".fat")
                    subprocess.run(
                        [
                            "lipo",
                            "-create",
                            str(native_so),
                            str(cross_so),
                            "-output",
                            str(fat),
                        ],
                        check=True,
                    )
                    fat.replace(native_so)

# For some reason zope is missing a top-level __init__.py when installed
# with pip, so we add it manually.
(bin_dir / "zope" / "__init__.py").touch()

# Remove test directories to reduce package size
for pattern in [
    "Crypto/SelfTest",
    "zope/interface/tests",
    "zope/interface/*/tests",
]:
    for match in bin_dir.glob(pattern):
        shutil.rmtree(match, ignore_errors=True)



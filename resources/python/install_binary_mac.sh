#!/usr/bin/env bash
# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Get python version
python_major_version=$(python -c "import sys; print(sys.version_info.major)")
python_minor_version=$(python -c "import sys; print(sys.version_info.minor)")
python_version="$python_major_version.$python_minor_version"

# Set paths
bin_dir="bin/$python_version/mac"
requirements="bin/$python_version/explicit_requirements.txt"

# Stops the script
set -e

# Delete current files
rm -rf $bin_dir
mkdir $bin_dir

# Install packages natively
pip install --target $bin_dir --no-deps -r $requirements

# Python 3.10+ is bundled with SGD Universal builds (SGD 1.9+), which run
# natively on both Intel and Apple Silicon. Some packages (e.g. cffi,
# zope.interface) do not publish universal wheels on PyPI, so we
# cross-compile them for the opposite architecture using ARCHFLAGS and
# combine the results into universal binaries with lipo.
# This works on any macOS machine without needing an arm64 runner.
#
# Python 3.9 and below are bundled with older Intel-only SGD builds. On
# Apple Silicon those SGD versions run entirely under Rosetta 2, so
# x86_64-only .so files are correct - no universal binaries needed.
if [ "$python_minor_version" -ge 10 ]; then
    tmp_cross=$(mktemp -d)
    trap "rm -rf $tmp_cross" EXIT

    native_arch=$(python -c "import platform; print(platform.machine())")
    if [ "$native_arch" = "arm64" ]; then
        cross_arch="x86_64"
    else
        cross_arch="arm64"
    fi

    echo "Native arch: $native_arch - cross-compiling for: $cross_arch"

    ARCHFLAGS="-arch $cross_arch" pip install \
        --target "$tmp_cross" \
        --no-deps \
        --no-binary cffi \
        --no-binary zope.interface \
        -r "$requirements"

    find "$tmp_cross" -name "*.so" | while read cross_so; do
        rel_path="${cross_so#$tmp_cross/}"
        native_so="$bin_dir/$rel_path"
        if [ -f "$native_so" ]; then
            if ! file "$native_so" | grep -q "universal binary"; then
                echo "Creating universal binary: $rel_path"
                lipo -create "$native_so" "$cross_so" -output "${native_so}.fat"
                mv "${native_so}.fat" "$native_so"
            fi
        fi
    done
fi

# For some reason zope is missing a top level init file when installed with
# pip, so we're adding it.
touch $bin_dir/zope/__init__.py

# Remove tests to thin out the packages
rm -rf $bin_dir/Crypto/SelfTest
rm -rf $bin_dir/zope/interface/tests
rm -rf $bin_dir/zope/interface/*/tests

# Add bin dir to repo
git add $bin_dir

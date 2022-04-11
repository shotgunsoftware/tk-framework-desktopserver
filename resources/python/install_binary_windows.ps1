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
$python_major_version = python -c "import sys; print(sys.version_info.major)"
$python_minor_version = python -c "import sys; print(sys.version_info.minor)"
$python_version = $python_major_version  + "." + $python_minor_version

# Set paths
$bin_dir = "bin/$python_version/win"
$requirements = "bin/$python_version/explicit_requirements.txt"

# Delete current files
Remove-Item -LiteralPath $bin_dir -Force -Recurse -ErrorAction Ignore
mkdir $bin_dir

# Install packages
python build/pip install --target $bin_dir --no-deps -r $requirements

# Remove tests to thin out the packages
Remove-Item -LiteralPath $bin_dir\Crypto\SelfTest -Force -Recurse -ErrorAction Ignore
Remove-Item -LiteralPath $bin_dir\zope\interface\tests -Force -Recurse -ErrorAction Ignore
Remove-Item -LiteralPath $bin_dir\zope\interface\common\tests -Force -Recurse -ErrorAction Ignore

# For some reason zope is missing a top level init file when installed with
# pip, so we're adding it.
ni $bin_dir\zope\__init__.py

# Add bin dir to repo
git add $bin_dir

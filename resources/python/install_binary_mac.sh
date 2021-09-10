# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

for PY_VERSION in 2.7 3.7
do
  case "$PY_VERSION" in
    2.7) PYTHON_BIN="/Applications/Shotgun.app/Contents/Resources/Python/bin/python" ;;
    3.7) PYTHON_BIN="/Applications/Shotgun.app/Contents/Resources/Python3/bin/python" ;;
  esac

  bin_dir="bin/$PY_VERSION/mac"
  requirements="bin/$PY_VERSION/explicit_requirements.txt"

  rm -rf $bin_dir
  mkdir $bin_dir
  $PYTHON_BIN build/pip install --target $bin_dir --no-deps -r $requirements

  # For some reason zope is missing a top level init file when installed with
  # pip, so we're adding it.
  touch $bin_dir/zope/__init__.py

  # Remove tests to thin out the packages
  rm -rf $bin_dir/Crypto/SelfTest
  rm -rf $bin_dir/zope/interface/tests
  rm -rf $bin_dir/zope/interface/*/tests

  git add $bin_dir
done

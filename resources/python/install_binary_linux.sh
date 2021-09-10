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
    2.7) PYTHON_BIN="/opt/Shotgun/Python/bin/python" ;;
    3.7) PYTHON_BIN="/opt/Shotgun/Python3/bin/python" ;;
  esac

  rm -rf bin/$PY_VERSION/linux

  # gcc has trouble finding out libpython2.7.so, we're adding its folder
  # to the link library path before invoking pip. Also, we're not using the
  # OS python because CentOS 5/6 do not ship with a version of SSL/TLS supported
  # by pypi.
  LDFLAGS=-L/opt/Shotgun/Python/lib $PYTHON_BIN build/pip install --target bin/$PY_VERSION/linux --no-deps -r bin/$PY_VERSION/explicit_requirements.txt

  # For some reason zope is missing a top level init file when installed with
  # pip, so we're adding it.
  touch bin/$PY_VERSION/linux/zope/__init__.py

  # Remove tests to thin out the packages
  rm -rf bin/$PY_VERSION/linux/Crypto/SelfTest
  rm -rf bin/$PY_VERSION/linux/zope/interface/tests
  rm -rf bin/$PY_VERSION/linux/zope/interface/*/tests

  git add bin/$PY_VERSION/linux

done

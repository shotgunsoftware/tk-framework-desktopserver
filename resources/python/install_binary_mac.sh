# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

git rm -rf bin/mac
rm -rf bin/mac
/Applications/Shotgun.app/Contents/Resources/Python/bin/python build/pip install --target bin/mac --no-deps -r bin/explicit_requirements.txt

# For some reason zope is missing a top level init file when installed with
# pip, so we're adding it.
touch bin/mac/zope/__init__.py

# Remove tests to thin out the packages
rm -rf bin/mac/Crypto/SelfTest

rm -rf bin/mac/zope/interface/tests
rm -rf bin/mac/zope/interface/*/tests

git add bin/mac
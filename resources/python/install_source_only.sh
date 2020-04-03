# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

git rm -rf source
rm -rf source
git reset HEAD source/explicit_requirements.txt
git checkout HEAD -- source/explicit_requirements.txt
PYTHONPATH=$PWD/build /Applications/Shotgun.app/Contents/Resources/Python/bin/python build/pip install --target source --no-deps -r source/explicit_requirements.txt

# We're thinning out the packages by removing unit tests.
rm -rf source/autobahn/test
rm -rf source/autobahn/*/test

rm -rf source/twisted/test
rm -rf source/twisted/*/test
rm -rf source/twisted/*/*/test

rm -rf source/automat/_test

rm -rf source/hyperlink/test

rm -rf source/incremental/tests

# In twisted.internet.unix, there is a mixin which we don't use that allows to copy file descriptors
# into other processes, which we don't require. That module is compiled, so we'll delete it.
rm source/twisted/python/_sendmsg.so

git add source
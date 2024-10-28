# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

echo "----------------------------------------------------"
echo "Get python version"

python_major_version=$(python -c "import sys; print(sys.version_info.major)")
python_minor_version=$(python -c "import sys; print(sys.version_info.minor)")
python_version="$python_major_version.$python_minor_version"

echo "Python version is $python_version"

echo "----------------------------------------------------"
echo "Set base paths"

requirements_filename="explicit_requirements.txt"
package_filename="pkgs.zip"
source_dir="src/$python_version"
source_requirements="$source_dir/$requirements_filename"

echo "Source Dir: $source_dir"
echo "Source Requirements: $source_requirements"

echo "----------------------------------------------------"
echo "Remove current packages"

find $source_dir/* ! -name $package_filename ! -name $requirements_filename -maxdepth 1 -exec rm -rf {} +

echo "----------------------------------------------------"
echo "Install new packages"

pip install --upgrade pip setuptools wheel

pip install \
  --target $source_dir \
  --no-deps \
  -r $source_requirements

echo "----------------------------------------------------"
echo "Remove unnecessary files"

rm -Rf $source_dir/autobahn/test
rm -Rf $source_dir/autobahn/*/test
rm -Rf $source_dir/twisted/test
rm -Rf $source_dir/twisted/*/test
rm -Rf $source_dir/twisted/*/*/test
rm -Rf $source_dir/automat/_test
rm -Rf $source_dir/hyperlink/test
rm -Rf $source_dir/incremental/tests

# In twisted.internet.unix, there is a mixin which we don't use that allows to copy file descriptors
# into other processes, which we don't require. That module is compiled, so we'll delete it.
rm -Rf $source_dir/twisted/python/_sendmsg.so

# Compress all files
pushd $source_dir
zip -q -r pkgs.zip ./*
popd

# Remove files
find $source_dir/* ! -name $package_filename ! -name $requirements_filename -maxdepth 1 -exec rm -rf {} +

echo "----------------------------------------------------"
echo "Adding new files to git"
git add $source_dir

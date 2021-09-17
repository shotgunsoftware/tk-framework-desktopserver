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
echo "Set base paths"

requirements_filename="explicit_requirements.txt"
build_dir=$PWD/build
python_2_executable="/Applications/Shotgun.app/Contents/Resources/Python/bin/python"
python_3_executable="/Applications/Shotgun.app/Contents/Resources/Python3/bin/python"

for py_version in 2.7 3.7
do
  echo "===================================================="
  echo "Set paths for $py_version"

  source_dir="src/$py_version"
  source_requirements="$source_dir/$requirements_filename"

  if [ "$py_version" = "2.7" ]
  then
    python_executable=$python_2_executable
  elif [ "$py_version" = "3.7" ]
  then
    python_executable=$python_3_executable
  fi

  echo "----------------------------------------------------"
  echo "Remove current packages"

  find $source_dir/* ! -name $requirements_filename -maxdepth 1 -exec rm -rf {} +

  echo "----------------------------------------------------"
  echo "Install new packages"

  PYTHONPATH=$build_dir \
    $python_executable \
    build/pip install \
    --target $source_dir \
    --no-deps \
    -r $source_requirements

  echo "----------------------------------------------------"
  echo "Remove unnecessary files"

  rm -rf $source_dir/autobahn/test
  rm -rf $source_dir/autobahn/*/test
  rm -rf $source_dir/twisted/test
  rm -rf $source_dir/twisted/*/test
  rm -rf $source_dir/twisted/*/*/test
  rm -rf $source_dir/automat/_test
  rm -rf $source_dir/hyperlink/test
  rm -rf $source_dir/incremental/tests

  # In twisted.internet.unix, there is a mixin which we don't use that allows to copy file descriptors
  # into other processes, which we don't require. That module is compiled, so we'll delete it.
  rm -rf $source_dir/twisted/python/_sendmsg.so

  echo "----------------------------------------------------"
  echo "Adding new files to git"
  git add $source_dir
done

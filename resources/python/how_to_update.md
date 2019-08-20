How to update 3rd party packages for the browser integration
------------------------------------------------------------

1. Update the list of packages to use
2. Run the update script on the first platform
3. Run the update script with `--bin-only` of the other two, as the python based packages have
   already been updated in step 2.

# Updating the list of package to use.

The list of top level dependencies is inside `requirements.txt`. Update this list if a security
issue is flagged and a module needs to be updated.

# Installing and adding to git the packages to use.

Run `update_packages.py` with any Python interpreter. The script will then use the Python interpreter from the Shotgun Desktop. It assumes the Shotgun Desktop is installed at the default location.

A note about the build folder
-----------------------------

The build folder was created with `virtualenv` by running `virtualenv build` in this folder,
nothing fancier.
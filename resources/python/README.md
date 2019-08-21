How to update 3rd party packages for the browser integration
------------------------------------------------------------

- Update the high-level list of packages to use inside `requirements.txt`
- Run `update_requirements.py`. This will bake the official versions of each
   package we need to install for each platform and in which folder.
- Run `install_source_only.sh`
- Run the `install_binary_*.*` scripts on their respective platform.

# Updating the list of package to use.

The list of top level dependencies is inside `requirements.txt`. Update this list if a security
issue is flagged and a module needs to be updated.

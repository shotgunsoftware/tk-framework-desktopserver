# Toolkit Framework Desktop Server

This framework manages the integration between SG Desktop and SG Web 
(browser integration).

Officially Supported Python Versions:
- Mac 
  - 2.7.18
  - 3.7.12
  - 3.9.10
- Windows 
  - 2.7.18
  - 3.7.9
  - 3.9.10
- Linux: 
  - 2.7.18
  - 3.7.12
  - 3.9.10

## How to update dependencies

1. Create a virtualenv for every python version 2.7, 3.7, 3.9

2. Update the packages to use inside:
   - `resources/python/requirements/2.7/requirements.txt`
   - `resources/python/requirements/3.7/requirements.txt`
   - `resources/python/requirements/3.9/requirements.txt`

3. For pythonExecute the script `resources/python/update_requirements.py --clean-pip` with python 2.7 and 3.7 (we highly recommend to use virtualenv and upgrade pip version).

   This will bake the official versions of each package we need to install for each platform and in which folder.

4. Run `resources/python/install_source_only.sh`

5. Push changes to the repository 

6. Run the `resources/python/install_binary_*.*` scripts on their respective platform and push the changes to the repository in every one.

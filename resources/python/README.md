# Manage bundled Python third party libraries

This document describes the process for updating the Python third party libraries
bundled in the `bin` and `src` directories.

## CI Automation

This process is fully taken care of by **CI automation** under the
[pipelines](pipelines/pipelines.yml) file.

### How to trigger the regeneration pipeline

Open a Pull Request from any branch that does **not** end with `-automated` or
`-no-rebuild`. The pipeline will:

1. Regenerate all source and binary requirements for every supported Python
   version and OS.
2. Commit the results to a new branch named `<your-branch>-automated`.
3. Push the branch and open a PR for review.

### Opting out of the regeneration pipeline

Sometimes you want to open a PR without triggering the package regeneration
(e.g. a documentation or CI-only change). Simply name your branch with the
`-no-rebuild` suffix:

```shell
git switch -c ticket/SG-12345-fix-docs-no-rebuild
```

The CI tests will still run normally - only the regen jobs are skipped.

### Why the `-automated` branch does not re-trigger the pipeline

When the pipeline pushes the `-automated` branch and opens a PR for it, that
PR would normally queue the pipeline again and create an
`<your-branch>-automated-automated` branch. This is prevented by a runtime
condition in [pipelines.yml](pipelines/pipelines.yml): all regen jobs are
skipped when `System.PullRequest.SourceBranch` ends with `-automated` or
`-no-rebuild`.

> [!Note]
> The `install_binary_mac.sh` script automatically produces universal binaries
> for Python 3.10+ by cross-compiling architecture-specific packages (such as
> [CFFI](https://pypi.org/project/cffi) and
> [Zope.interface](https://pypi.org/project/zope.interface)) using `ARCHFLAGS`
> and combining the results with `lipo`. No Apple Silicon machine is required -
> the script works correctly on any macOS, including Intel CI runners (SG-40224).


## Support Python versions

Officially Supported Python Versions:

- macOS
  - 3.7.16
  - 3.9.16
  - 3.10.13
  - 3.11.9
  - 3.13
- Windows 
  - 3.7.9
  - 3.9.13
  - 3.10.11
  - 3.11.9
  - 3.13
- Linux: 
  - 3.7.16
  - 3.9.16
  - 3.10.13
  - 3.11.9
  - 3.13

This is aligned with the supported [Flow Production Tracking desktop app versions](https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_si_platform_supported_versions_html).

> [!Note]
> For macOS, Python versions 3.10+ are supported for both Intel (`x86_64`) and
> Silicon (`arm64`) architectures since FPTR desktop versions 1.9+ are delivered
> as Universal builds.


## Step by step manual update process

For this documentation the examples are using the following locations, you can
use whatever work best for you:

- Virtualenvs base folder
  - macOS and Linux: `$HOME/venv`
  - Windows: `$HOME\venv`
- Cloned repositories base folder
  - macOS and Linux: `$HOME/instances`
  - Windows: `$HOME\instances`
- Python installation in windows:
  - C:\python\3.X

### Create a branch in the repository  

You can choose any operating system to create the branch

Linux or macOS:

```shell
git clone git@github.com:shotgunsoftware/tk-framework-desktopserver.git $HOME/instances/tk-framework-desktopserver
cd $HOME/instances/tk-framework-desktopserver
git checkout -b BRANCH_NAME
git push --set-upstream origin BRANCH_NAME
```

Windows:

```shell
git clone git@github.com:shotgunsoftware/tk-framework-desktopserver.git $HOME\instances\tk-framework-desktopserver
cd $HOME\instances\tk-framework-desktopserver
git checkout -b BRANCH_NAME
git push --set-upstream origin BRANCH_NAME
```

### Clone and checkout the repository in every Operating System

Linux and macOS:

```shell
git clone git@github.com:shotgunsoftware/tk-framework-desktopserver.git $HOME/instances/tk-framework-desktopserver
cd $HOME/instances/tk-framework-desktopserver
git checkout BRANCH_NAME
```

Windows:

```shell
git clone git@github.com:shotgunsoftware/tk-framework-desktopserver.git $HOME\instances\tk-framework-desktopserver
cd $HOME\instances\tk-framework-desktopserver
git checkout BRANCH_NAME
```

### Create virtualenvs

Create a virtualenv for every supported python version in every operating 
system.

Linux and macOS:

We highly recommend to use [pyenv](https://github.com/pyenv/pyenv).

```shell
rm -Rf $HOME/venv/tk-framework-desktopserver-37
pyenv install 3.7.16
pyenv shell 3.7.16
python -m pip install -U pip virtualenv
python -m virtualenv $HOME/venv/tk-framework-desktopserver-37 

# Repeat steps for Python 3.9 and 3.10
```

Windows:
  - Use an admin powershell console.
  - Install python 3.7.9 from https://www.python.org/ftp/python/3.7.9/python-3.7.9-amd64.exe in C:\python\3.7.9
  - Install python 3.9.13 from https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe in C:\python\3.9.13
  - Install python 3.10.11 from https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe in C:\python\3.10.11

```shell
if (test-path $HOME\venv\tk-framework-desktopserver-37) {
  Remove-Item $HOME\venv\tk-framework-desktopserver-37 -Recurse -Force
}
C:\python\3.7.9\python.exe -m pip install -U pip virtualenv
C:\python\3.7.9\python.exe -m virtualenv $HOME\venv\tk-framework-desktopserver-37 

# Repeat steps for Python 3.9 and 3.10
```

### In macOS, update requirements.txt files

- resources/python/requirements/3.7/requirements.txt
  ```shell
  # Activate python 3.7 virtualenv
  source $HOME/venv/tk-framework-desktopserver-37/bin/activate

  # Copy requirements.txt to temporal folder
  cp $HOME/instances/tk-framework-desktopserver/resources/python/requirements/3.7/requirements.txt /tmp/requirements.txt
  
  # Chdir to temporal folder
  cd /tmp
  
  # Replace the versions numbers of the requirements.txt file
  sed -i 's/==.*$//' requirements.txt
  
  # Create a temporal folder
  mkdir temporal_requirements
  
  # Install the requirements in the new temporal folder
  pip install -r requirements.txt -t temporal_requirements
  
  # Get the list of packages installed versions
  pip list --path temporal_requirements
  
  # Compare versions and update the file $HOME/instances/tk-framework-desktopserver/resources/python/requirements/3.7/requirements.txt
  
  # Cleanup everything
  rm -Rf temporal_requirements
  rm -f requirements.txt
  ```

- Repeat steps for Python 3.9 and 3.10

### In macOS, activate virtualenvs and execute the script `update_requirements.py` 

This will bake the official versions of each package we need to install in 
every platform (Python Version, Operating System).

```shell
cd $HOME/instances/tk-framework-desktopserver/resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
python update_requirements.py --clean-pip

# Repeat steps for Python 3.9 and 3.10
```

### In macOS, activate virtualenvs and execute the script `install_source_only.sh` 

```shell
cd $HOME/instances/tk-framework-desktopserver/resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
bash install_source_only.sh

# Repeat steps for Python 3.9 and 3.10
```

### In macOS, push changes to the repository

```shell
git add .
git commit -am "Update source requirements."
git push
```

### Install the binaries for each OS

On each operating system, activate virtualenvs, execute the corresponding script
to install binaries, and then push changes to the repository.

#### Linux

```shell
cd $HOME/instances/tk-framework-desktopserver
git pull
cd resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
bash install_binary_linux.sh
git add .
git commit -am "Update binary requirements in Linux Python 3.7"
git push

# Repeat steps for Python 3.9 and 3.10
```


#### Windows
  - Use an admin powershell console.

```shell
cd $HOME\instances\tk-framework-desktopserver\resources\python
& "$HOME\venv\tk-framework-desktopserver-37\Scripts\activate.ps1"
.\install_binary_windows.ps1
git add .
git commit -am "Update binary requirements in Windows Python 3.7"
git push

# Repeat steps for Python 3.9 and 3.10
```


#### macOS

> [!Note]
> The script works on any macOS machine (Intel or Apple Silicon). For Python
> 3.10+, it automatically produces universal binaries by cross-compiling
> architecture-specific packages and combining them with `lipo`.

```shell
cd $HOME/instances/tk-framework-desktopserver/resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
bash install_binary_mac.sh
git add .
git commit -am "Update binary requirements in macOS Python 3.7"
git push

# Repeat steps for each supported Python version
```

# Toolkit Framework Desktop Server

This framework manages the integration between Flow Production Tracking and Flow Production Tracking Web 
(browser integration).

Officially Supported Python Versions:

- macOS
  - 3.7.16
  - 3.9.16
  - 3.10.13
- Windows 
  - 3.7.9
  - 3.9.13
  - 3.10.11
- Linux: 
  - 3.7.16
  - 3.9.16
  - 3.10.13

## CI Automation

These steps are now taken care by CI automation under the [pipelines](pipelines/pipelines.yml) file.
When changes are pushed to GitHub, it will create a new branch with the same name with the `-automated` prefix.
Please review the changes and open a PR.

## How to manually update dependencies

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

### In every Operating System, activate virtualenvs and execute the corresponding script to install binaries  and then push changes to repository

#### macOS

```shell
cd $HOME/instances/tk-framework-desktopserver/resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
bash install_binary_mac.sh
git add .
git commit -am "Update binary requirements in macOS Python 3.7"
git push

# Repeat steps for Python 3.9 and 3.10
```

> Important Notice for Apple Silicon: CI uses a Intel macOS to install the binary requirements.
> There are two specific ones that don't have wheels with fat binaries: CFFI and Zope.interface.
> For them, we recommend to get `_cffi_backend.cpython-310-darwin.so` and `_zope_interface_coptimizations.cpython-310-darwin.so`
> from both architectures and combine them into a fat binary using MacOS `lipo` tool
> and replace the files in this repository when upgrading any of these requirements.

```shell
lipo _cffi_x86_64_file.so _cffi_arm64_file.so -create -output _cffi_backend.cpython-310-darwin.so
lipo _zope_x86_64_file.so _zope_arm64_file.so -create -output _zope_interface_coptimizations.cpython-310-darwin.so
```

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

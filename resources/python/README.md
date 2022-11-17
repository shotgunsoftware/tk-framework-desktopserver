# Toolkit Framework Desktop Server

This framework manages the integration between SG Desktop and SG Web 
(browser integration).

Officially Supported Python Versions:
- Mac 
  - 2.7.18
  - 3.7.15
  - 3.9.15
- Windows 
  - 2.7.18
  - 3.7.9
  - 3.9.13
- Linux: 
  - 2.7.18
  - 3.7.15
  - 3.9.15

## How to update dependencies

### Create Jira ticket and git branch

- Create a Jira in `Ecosystem ShotGrid` board https://jira.autodesk.com/secure/RapidBoard.jspa?projectKey=SG&rapidView=12718
- Create a branch in  https://github.com/shotgunsoftware/tk-framework-desktopserver

### Create virtualenvs

For Windows 10, Centos 7 and Mac, create 3 virtualenvs:
- tk-framework-desktopserver-2-7-18 with python version 2.7.18
- tk-framework-desktopserver-3-7-12 with python version 3.7.12 (could be different version in windows)
- tk-framework-desktopserver-3-9-10 with python version 3.9.10 (could be different version in windows)

We highly recommend use [pyenv](https://github.com/pyenv/pyenv).

**Note for Windows:** 
- Use an admin powershell console.
- Install pyenv with https://pyenv-win.github.io/pyenv-win/

Example for Mac and Linux:

```shell
pyenv install 2.7.18
$HOME/.pyenv/versions/2.7.18/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/2.7.18/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-2-7-18 
```

```shell
pyenv install 3.7.12
$HOME/.pyenv/versions/3.7.12/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.7.12/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-3-7-12 
```

```shell
pyenv install 3.9.10
$HOME/.pyenv/versions/3.9.10/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.9.10/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-3-9-10 
```
### Update requirements

In MAC, update the packages in requirements files:

- `resources/python/requirements/2.7/requirements.txt`
- `resources/python/requirements/3.7/requirements.txt`
- `resources/python/requirements/3.9/requirements.txt`

### Execute the script `update_requirements.py` 

In MAC, execute the script `update_requirements.py` with every virtualenv:

```shell
cd resources/python
python update_requirements.py --clean-pip
```

This will bake the official versions of each package we need to install in 
every platform (Python Version, Operating System).

### Execute the script `install_source_only.sh`

In MAC, execute the script `install_source_only.sh` with every virtualenv:

```shell
cd resources/python
bash install_source_only.sh
```

### Push changes to the repository

- Git commit
- Git push

### Install binary in Mac

- In MAC, execute the script `install_binary_mac.sh` with every virtualenv:
  ```shell
  cd resources/python
  bash install_binary_mac.sh
  ```

- Push changes to the repository

### Install binary in Windows 10

- In Windows inside a powershell as admin, execute the script `install_binary_windows.bat` with every virtualenv:

```shell
cd resources/python
install_binary_windows.ps1
```

### Install binary in CentOS 7

- In CentOS, execute the script `install_binary_linux.sh` with every virtualenv:
  ```shell
  cd resources/python
  bash install_binary_linux.sh
  ```
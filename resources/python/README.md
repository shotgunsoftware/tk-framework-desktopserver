# Toolkit Framework Desktop Server

This framework manages the integration between SG Desktop and SG Web 
(browser integration).

Officially Supported Python Versions:
- Mac 
  - 3.9.15
- Windows 
  - 3.9.13
- Linux: 
  - 3.9.15

## How to update dependencies

### Create Jira ticket and git branch

- Create a Jira in `Ecosystem ShotGrid` board https://jira.autodesk.com/secure/RapidBoard.jspa?projectKey=SG&rapidView=12718
- Create a branch in  https://github.com/shotgunsoftware/tk-framework-desktopserver

### Create virtualenvs

For Windows 10, Centos 7/Rocky 8 and Mac, create a virtualenv `tk-framework-desktopserver-39` with latest python version 3.9.x

We highly recommend use [pyenv](https://github.com/pyenv/pyenv).

**Note for Windows:** 
- Use an admin powershell console.
- Install pyenv with https://pyenv-win.github.io/pyenv-win/

Example for Mac and Linux:

```shell
pyenv install 3.9.15
$HOME/.pyenv/versions/3.9.15/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.9.15/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-3-9-15 
```
### Update requirements

In MAC, update the packages in requirements files:

- `resources/python/requirements/3.9/requirements.txt`

### Execute the script `update_requirements.py` 

In MAC, execute the script `update_requirements.py`:

```shell
cd resources/python
python update_requirements.py --clean-pip
```

This will bake the official versions of each package we need to install in 
every Operating System.

### Execute the script `install_source_only.sh`

In MAC, execute the script `install_source_only.sh`:

```shell
cd resources/python
bash install_source_only.sh
```

### Push changes to the repository

- Git commit
- Git push

### Install binary in Mac

- In MAC, execute the script `install_binary_mac.sh`:
  ```shell
  cd resources/python
  bash install_binary_mac.sh
  ```

- Push changes to the repository

### Install binary in Windows 10

- In Windows inside a powershell as admin, execute the script `install_binary_windows.ps1`:

```shell
cd resources/python
install_binary_windows.ps1
```

### Install binary in CentOS 7

- In CentOS, execute the script `install_binary_linux.sh`:
  ```shell
  cd resources/python
  bash install_binary_linux.sh
  ```
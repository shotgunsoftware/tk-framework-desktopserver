# Toolkit Framework Desktop Server

This framework manages the integration between SG Desktop and SG Web 
(browser integration).

Officially Supported Python Versions:

- Mac 
  - 3.7.16
  - 3.9.16
- Windows 
  - 3.7.9
  - 3.9.13
- Linux: 
  - 3.7.16
  - 3.9.16

## How to update dependencies

Create a Jira in `Ecosystem ShotGrid` board https://jira.autodesk.com/secure/RapidBoard.jspa?projectKey=SG&rapidView=12718
Create a branch in https://github.com/shotgunsoftware/tk-framework-desktopserver

| Name               | Description                                     | Operating Systems   | Command |
|--------------------|-------------------------------------------------|---------------------|---------|
| Create virtualenvs | For every operating system, create a virtualenv | Windows, Mac, Linux |         |
|                    | for every supported python version              |                     |         |


### Create virtualenvs

For every operating system (Windows, Centos|Rocky and Mac), create 2 virtualenvs:

- tk-framework-desktopserver-37 with python version 3.7
- tk-framework-desktopserver-39 with python version 3.9

We highly recommend to use [pyenv](https://github.com/pyenv/pyenv).

**Note for Windows:** 
- Use an admin powershell console.
- Install pyenv with https://pyenv-win.github.io/pyenv-win/

Example for Mac and Linux:

```shell
rm -Rf $HOME/venv/tk-framework-desktopserver-37
pyenv install 3.7.16
$HOME/.pyenv/versions/3.7.16/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.7.16/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-37 
```

```shell
rm -Rf $HOME/venv/tk-framework-desktopserver-39
pyenv install 3.9.16
$HOME/.pyenv/versions/3.9.16/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.9.16/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-39 
```

Example for Windows:

```shell
rmdir /S /Q %HOMEPATH%\venv\tk-framework-desktopserver-37
pyenv install 3.7.9
%HOMEPATH%\.pyenv\pyenv-win\versions\3.7.9\python.exe -m pip install -U pip virtualenv
%HOMEPATH%\.pyenv\pyenv-win\versions\3.7.9\python.exe -m virtualenv %HOMEPATH%\venv\tk-framework-desktopserver-37 
```

```shell
rmdir /S /Q %HOMEPATH%\venv\tk-framework-desktopserver-39
pyenv install 3.9.13
%HOMEPATH%\.pyenv\pyenv-win\versions\3.9.13\python.exe -m pip install -U pip virtualenv
%HOMEPATH%\.pyenv\pyenv-win\versions\3.9.13\python.exe -m virtualenv %HOMEPATH%\venv\tk-framework-desktopserver-39 
```

### Update requirements

In MAC, update the packages in requirements files:

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

- In Windows inside a powershell as admin, execute the script `install_binary_windows.ps1` with every virtualenv:

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
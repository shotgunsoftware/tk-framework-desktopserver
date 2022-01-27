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



    ```shell
    cd resources/python
    bash install_source_only.sh
    ```

5. Push changes to the repository 

### The following steps must be executed in Mac, Windows and Linux

#### In Windows

In an admin powershell console run:

```shell
cd resources/python
install_binary_winsource_only.sh
```

Run the script `resources/python/install_binary_*.*` scripts on their respective platform and push the changes to the repository in every one.

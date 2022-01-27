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

For Windows 10, Centos 7 and Mac, create 3 virtualenvs with every python 
version 2.7, 3.7, 3.9. We highly recommend use (pyenv)[https://github.com/pyenv/pyenv].

**Note for Windows:** 
- Use an admin powershell console.
- Install pyenv with https://pyenv-win.github.io/pyenv-win/

Example for Mac and Linux:

```shell
pyenv install 2.7.18
.pyenv/versions/2.7.18 -m pip install -U pip virtualenv
.pyenv/versions/2.7.18 -m virtualenv $HOME/venv/tk-framework-desktopserver-2-7-18 
```

```shell
pyenv install 3.7.12
.pyenv/versions/3.7.12 -m pip install -U pip virtualenv
.pyenv/versions/3.7.12 -m virtualenv $HOME/venv/tk-framework-desktopserver-3-7-12 
```

```shell
pyenv install 3.9.10
.pyenv/versions/3.9.10 -m pip install -U pip virtualenv
.pyenv/versions/3.9.10 -m virtualenv $HOME/venv/tk-framework-desktopserver-3-9-10 
```

cd resources/python
python update_requirements.py --clean-pip
```


### The following steps must be executed in Mac.


2. Update the packages to use inside:
   - `resources/python/requirements/2.7/requirements.txt`
   - `resources/python/requirements/3.7/requirements.txt`
   - `resources/python/requirements/3.9/requirements.txt`

3. Execute the script `update_requirements.py` with every python version
   2.7, 3.7, 3.9.

   ```shell
   cd resources/python
   python update_requirements.py --clean-pip
   ```

   This will bake the official versions of each package we need to install in 
   every platform (Python Version, Operating System).

4. Execute the script `install_source_only.sh` with every python version
   2.7, 3.7, 3.9.

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

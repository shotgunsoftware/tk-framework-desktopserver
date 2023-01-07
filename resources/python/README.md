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

For this documentation the examples are using the following locations, you can
use whatever work best for you:

- Virtualenvs base folder
  - Mac and Linux: `$HOME/venv`
  - Windows: `$HOME\venv`
- Cloned repositories base folder
  - Mac and Linux: `$HOME/instances`
  - Windows: `$HOME\instances`

### Create a branch in the repository  

You can choose any operating system to create the branch

Linux or Mac:

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

Linux and Mac:

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

We highly recommend to use [pyenv](https://github.com/pyenv/pyenv).

Linux and Mac:

```shell
rm -Rf $HOME/venv/tk-framework-desktopserver-37
pyenv install 3.7.16
$HOME/.pyenv/versions/3.7.16/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.7.16/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-37 

rm -Rf $HOME/venv/tk-framework-desktopserver-39
pyenv install 3.9.16
$HOME/.pyenv/versions/3.9.16/bin/python -m pip install -U pip virtualenv
$HOME/.pyenv/versions/3.9.16/bin/python -m virtualenv $HOME/venv/tk-framework-desktopserver-39 
```

Windows:
  - Use an admin powershell console.
  - Install pyenv with https://pyenv-win.github.io/pyenv-win/

```shell
rmdir /S /Q %HOMEPATH%\venv\tk-framework-desktopserver-37
pyenv install 3.7.9
%HOMEPATH%\.pyenv\pyenv-win\versions\3.7.9\python.exe -m pip install -U pip virtualenv
%HOMEPATH%\.pyenv\pyenv-win\versions\3.7.9\python.exe -m virtualenv %HOMEPATH%\venv\tk-framework-desktopserver-37 

rmdir /S /Q %HOMEPATH%\venv\tk-framework-desktopserver-39
pyenv install 3.9.13
%HOMEPATH%\.pyenv\pyenv-win\versions\3.9.13\python.exe -m pip install -U pip virtualenv
%HOMEPATH%\.pyenv\pyenv-win\versions\3.9.13\python.exe -m virtualenv %HOMEPATH%\venv\tk-framework-desktopserver-39 
```

### In Mac, update requirements.txt files

- resources/python/requirements/3.7/requirements.txt
  ```shell
  # Activate python 3.7 virtualenv
  source $HOME/venv/tk-framework-desktopserver-37/bin/activate

  # Copy requirements.txt to temporal folder
  cp $HOME/instances/desktopserver-37/resources/python/requirements/3.7/requirements.txt /tmp/requirements.txt
  
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
  
  # Compare versions and update the file $HOME/instances/desktopserver-37/resources/python/requirements/3.7/requirements.txt
  
  # Cleanup everything
  rm -Rf temporal_requirements
  rm -f requirements.txt
  ```

- resources/python/requirements/3.9/requirements.txt
  ```shell
  # Activate python 3.9 virtualenv
  source $HOME/venv/tk-framework-desktopserver-39/bin/activate
  
  # Copy requirements.txt to temporal folder
  cp $HOME/instances/desktopserver-39/resources/python/requirements/3.9/requirements.txt /tmp/requirements.txt
  
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
  
  # Compare versions and update the file $HOME/instances/desktopserver-39/resources/python/requirements/3.9/requirements.txt
  
  # Cleanup everything
  rm -Rf temporal_requirements
  rm -f requirements.txt
  ```

### In Mac, activate virtualenvs and execute the script `update_requirements.py` 

This will bake the official versions of each package we need to install in 
every platform (Python Version, Operating System).

```shell
source $HOME/venv/tk-framework-desktopserver-37/bin/activate
cd $HOME/instance/tk-framework-desktopserver-37/resources/python
python update_requirements.py --clean-pip

source $HOME/venv/tk-framework-desktopserver-39/bin/activate
cd $HOME/instances/tk-framework-desktopserver-39/resources/python
python update_requirements.py --clean-pip
```

### In Mac, activate virtualenvs and execute the script `install_source_only.sh` 

```shell
source $HOME/venv/tk-framework-desktopserver-37/bin/activate
cd $HOME/venv/tk-framework-desktopserver-37/resources/python
bash install_source_only.sh

source $HOME/venv/tk-framework-desktopserver-39/bin/activate
cd $HOME/venv/tk-framework-desktopserver-39/resources/python
bash install_source_only.sh
```

### In Mac, push changes to the repository

```shell
git add .
git commit -am "Update source requirements."
git push
```

### In every Operating System, activate virtualenvs and execute the corresponding script to install binaries  and then push changes to repository

Mac

```shell
source $HOME/venv/tk-framework-desktopserver-37/bin/activate
cd $HOME/venv/tk-framework-desktopserver-37/resources/python
bash install_binary_mac.sh
git add .
git commit -am "Update binary requirements in Mac Python 3.7"
git push

source $HOME/venv/tk-framework-desktopserver-39/bin/activate
cd $HOME/venv/tk-framework-desktopserver-39/resources/python
bash install_binary_mac.sh
git add .
git commit -am "Update binary requirements in Mac Python 3.9"
git push
```

Linux

```shell
source $HOME/venv/tk-framework-desktopserver-37/bin/activate
cd $HOME/venv/tk-framework-desktopserver-37/resources/python
bash install_binary_linux.sh
git add .
git commit -am "Update binary requirements in Linux Python 3.7"
git push

source $HOME/venv/tk-framework-desktopserver-39/bin/activate
cd $HOME/venv/tk-framework-desktopserver-39/resources/python
bash install_binary_linux.sh
git add .
git commit -am "Update binary requirements in Linux Python 3.9"
git push
```

Windows
  - Use an admin powershell console.

```shell
%HOMEPATH%\venv\tk-framework-desktopserver-37\Scripts\activate.ps1
cd %HOMEPATH%\instances\tk-framework-desktopserver\resources\python
install_binary_windows.ps1
git add .
git commit -am "Update binary requirements in Windows Python 3.7"
git push

%HOMEPATH%\venv\tk-framework-desktopserver-39\Scripts\activate.ps1
cd %HOMEPATH%\instances\tk-framework-desktopserver\resources\python
install_binary_windows.ps1
git add .
git commit -am "Update binary requirements in Windows Python 3.9"
git push
```

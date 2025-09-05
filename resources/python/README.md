# Manage bundled Python third party libraries

This document describes the process for updating the Python third party libraries
bundled in the `bin` and `src` directories.

## CI Automation

This process is *almost* fully taken care of by **CI automation** under the
[pipelines](pipelines/pipelines.yml) file.
When changes are pushed to GitHub, it will create a new branch with the same
name adding the `-automated` suffix.
Please review the changes and open a PR.

> [!Important]
> **Wait! Did you say almost?**
>
> On one hand, Azure CI currently only provides Intel architecture macOS
> runners.
> On the other hand, there are two specific Python libraries that don't provide
> *Universal* wheels on pypi.org: [CFFI](https://pypi.org/project/cffi) and
> [Zope.interface](https://pypi.org/project/zope.interface).
>
> So unfortunately, our CI is not able to do it all for macOS at the moment
> (SG-40224).
> Once the CI has finished building the `-automated` branch, **you MUST check
> it out and manually run the
> [macOS for Apple silicon architecture (arm64)](#macos-for-apple-silicon-architecture-arm64) section**!


## Support Python versions

Officially Supported Python Versions:

- macOS
  - 3.7.16
  - 3.9.16
  - 3.10.13
  - 3.11.9
- Windows 
  - 3.7.9
  - 3.9.13
  - 3.10.11
  - 3.11.9
- Linux: 
  - 3.7.16
  - 3.9.16
  - 3.10.13
  - 3.11.9

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


#### macOS for Intel architecture (x86_64)

> [!Important]
> If you have an Apple Silicon computer, make sure to run Python in
> **Rosetta mode** (`arch -x86_64`).
> You might need to install a dedicated Python environment to accomplish this.

```shell
cd $HOME/instances/tk-framework-desktopserver/resources/python

source $HOME/venv/tk-framework-desktopserver-37/bin/activate
bash install_binary_mac.sh
git add .
git commit -am "Update binary requirements in macOS Python 3.7"
git push

# Repeat steps for Python 3.9 and 3.10
```


#### macOS for Apple silicon architecture (arm64)

> [!Note]
> Skip this section for Python versions 3.9 and below.

Unfortunately, some Python libraries are not distributed in Universal platform
format (*fat*), but are platform-specific.
For those libraries, you need to run the process a second time on an M1/M2/M3... computer and then generate Universal libraries.

> [!Warning]
> You need an Apple silicon computer for this task (ex: M1, M2, ...).
> Also, make sure your Python environment runs in **Native mode**.

> [!Important]
> Currently, only two libraries are known not to be distributed as Universal libraries.
> However, this may change, so please check if other `.so` files are present and adjust this document accordingly.

1.  Select the right folder and load the Python venv
    ```shell
    cd $HOME/instances/tk-framework-desktopserver/resources/python
    source $HOME/venv/tk-framework-desktopserver-310/bin/activate
    ```

1.  Confirm the current  `-darwin.so` are Intel-only platform (x86_64)
    * CFFI library
      ```shell
      $ file bin/3.10/mac/_cffi_backend.cpython-310-darwin.so
      Mach-O 64-bit bundle x86_64
      ```
    * Zope Interface library
      ```shell
      $ file bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so
      Mach-O 64-bit bundle x86_64
      ```

1.  Rename the `-darwin.so` files to `-x86_64.so`
    * CFFI library
      ```shell
      mv bin/3.10/mac/_cffi_backend.cpython-310-darwin.so _cffi_backend.cpython-310-x86_64.so
      ```
    * Zope Interface library
      ```shell
      mv bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so \
        _zope_interface_coptimizations.cpython-310-x86_64.so
      ```

1.  Execute the install script (in silicon mode)
    ```shell
    ./install_binary_mac.sh
    ```

1.  Confirm that the new `-darwin.so` are Silicon-only platform (arm64)
    * CFFI library
      ```shell
      $ file bin/3.10/mac/_cffi_backend.cpython-310-darwin.so
      Mach-O Mach-O 64-bit bundle arm64
      ```
    * Zope Interface library
      ```shell
      $ file bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so
      Mach-O 64-bit bundle arm64
      ```

1.  Rename the new `-darwin.so` files to `-arm64.so`
    * CFFI library
      ```shell
      mv bin/3.10/mac/_cffi_backend.cpython-310-darwin.so _cffi_backend.cpython-310-arm64.so
      ```
    * Zope Interface library
      ```shell
      mv bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so \
        _zope_interface_coptimizations.cpython-310-arm64.so
      ```

1.  Combine the two `.so` files into a Universal library using the native
    macOS `lipo` tool
    * CFFI library
      ```shell
      lipo _cffi_backend.cpython-310-x86_64.so _cffi_backend.cpython-310-arm64.so -create \
        -output bin/3.10/mac/_cffi_backend.cpython-310-darwin.so
      ```
    * Zope Interface library
      ```shell
      lipo _zope_interface_coptimizations.cpython-310-x86_64.so \
        _zope_interface_coptimizations.cpython-310-arm64.so -create -output \
        bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so
      ```

1.  Confirm that the `-darwin.so` files are now Universal with both platforms
    * CFFI library
      ```shell
      $ file bin/3.10/mac/_cffi_backend.cpython-310-darwin.so
      Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit bundle x86_64] [arm64:Mach-O 64-bit bundle arm64]
      (for architecture x86_64):     Mach-O 64-bit bundle x86_64
      (for architecture arm64):      Mach-O 64-bit bundle arm64
      ```
    * Zope Interface library
      ```shell
      $ file bin/3.10/mac/zope/interface/_zope_interface_coptimizations.cpython-310-darwin.so
      Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit bundle x86_64] [arm64:Mach-O 64-bit bundle arm64]
      (for architecture x86_64):     Mach-O 64-bit bundle x86_64
      (for architecture arm64):      Mach-O 64-bit bundle arm64
      ```

1.  Commit and Push

    ```shell
    git add bin/
    git commit -m "Update binary requirements in macOS Python 3.10 (Universal)"
    git push
    ```

> [!Important]
> Repeat the Process for each Python version 3.10+!

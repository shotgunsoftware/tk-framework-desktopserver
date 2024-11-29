Readme for tests
================

Required packages
-----------------
To install the required dependencies, just create a virtual environment and install tk-toolchain.

```shell
pip install https://github.com/shotgunsoftware/tk-toolchain/archive/master.zip
```

Also, in the same directory where this repository is located, you should clone the following repositories.

```shell
cd..
git clone git@github.com:shotgunsoftware/tk-framework-desktopclient.git
git clone git@github.com:shotgunsoftware/tk-shotgun.git
```

Running the test suite
-----------------------
Test suite uses pytest. To run all tests just execute

```shell
python -m pytest tests
```

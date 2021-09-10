:: Copyright (c) 2017 Shotgun Software Inc.
::
:: CONFIDENTIAL AND PROPRIETARY
::
:: This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
:: Source Code License included in this distribution package. See LICENSE.
:: By accessing, using, copying or modifying this work you indicate your
:: agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
:: not expressly granted therein are reserved by Shotgun Software Inc.


setlocal ENABLEDELAYEDEXPANSION
@echo OFF

FOR %%V IN (2.7 3.7) DO (

    IF %%V LSS 3 (
        set PYTHON_EXE="C:\Program Files\Shotgun\Python\python.exe"
    ) ELSE (
        set PYTHON_EXE="C:\Program Files\Shotgun\Python3\python.exe"
    )

    rmdir /s /q bin\%%V\win
    
    !PYTHON_EXE! build/pip install --target bin\%%V\win --no-deps -r bin\%%V\explicit_requirements.txt

    :: Remove tests to thin out the packages
    rmdir /s /q bin\%%V\win\Crypto\SelfTest
    rmdir /s /q bin\%%V\win\zope\interface\tests
    rmdir /s /q bin\%%V\win\zope\interface\common\tests

    :: For some reason zope is missing a top level init file when installed with
    :: pip, so we're adding it.
    copy nul bin\%%V\win\zope\__init__.py

    git add bin\%%V\win
)

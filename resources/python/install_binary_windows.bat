git rm -rf bin\win
rmdir /s /q bin\win

"C:\Program Files\Shotgun\Python\python.exe" build/pip install --target bin\win --no-deps -r binary_requirements.txt
touch bin/win/zope/__init__.py

# Remove tests to thin out the packages
rmdir /s /q bin\win\Crypto\SelfTest

rmdir /s /q bin\win\zope\interface\tests

rmdir /s /q bin\win\zope\interface\common\tests

copy nul bin\win\zope\__init__.py
git rm -rf bin/linux
rm -rf bin/linux
LDFLAGS=-L/opt/Shotgun/Python/lib /opt/Shotgun/Python/bin/python build/pip install --target bin/linux --no-deps -r binary_requirements.txt
touch bin/linux/zope/__init__.py

# Remove tests to thin out the packages
rm -rf bin/linux/Crypto/SelfTest

rm -rf bin/linux/zope/interface/tests
rm -rf bin/linux/zope/interface/*/tests
git rm -rf bin/mac
rm -rf bin/mac
/Applications/Shotgun.app/Contents/Resources/Python/bin/python build/pip install --target bin/mac --no-deps -r binary_requirements.txt
touch bin/mac/zope/__init__.py

# Remove tests to thin out the packages
rm -rf bin/mac/Crypto/SelfTest

rm -rf bin/mac/autobahn/test
rm -rf bin/mac/autobahn/*/test

rm -rf bin/mac/twisted/test
rm -rf bin/mac/twisted/*/test
rm -rf bin/mac/twisted/*/*/test

rm -rf bin/mac/zope/interface/tests
rm -rf bin/mac/zope/interface/*/tests
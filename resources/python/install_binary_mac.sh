git rm -rf bin/mac
rm -rf bin/mac
/Applications/Shotgun.app/Contents/Resources/Python/bin/pip install --target bin/mac --no-deps -r binary_requirements.txt
touch bin/mac/zope.interface/__init__.py
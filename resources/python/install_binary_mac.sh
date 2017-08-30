git rm -rf bin/mac
mkdir --parents bin/mac
/Applications/Shotgun.app/Contents/Resources/Python/bin/pip install --target bin/mac --no-deps -r binary_requirements.txt
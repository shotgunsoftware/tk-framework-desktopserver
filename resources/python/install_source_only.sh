git rm -rf source
rm -rf source
/Applications/Shotgun.app/Contents/Resources/Python/bin/python build/pip install --target source --no-deps -r source_only_requirements.txt

rm -rf source/autobahn/test
rm -rf source/autobahn/*/test

rm -rf source/twisted/test
rm -rf source/twisted/*/test
rm -rf source/twisted/*/*/test

# In twisted.internet.unix, there is a mixin which we don't use that allows to copy file descriptors
# into other processes, which we don't require. That module is compiled, so we'll delete it.
rm source/twisted/python/_sendmsg.so

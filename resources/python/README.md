# Toolkit Framework Desktop Server

This framework manages the integration between SG Desktop with SG Web (browser integration).

## Dependencies

| Package             | MAC PY2   | MAC PY3   | WIN PY2   | WIN PY3   | LINUX PY2 | LINUX PY3 |
| ------------------- | --------- | --------- | --------- | --------- | --------- | --------- |
| Automat             | 20.2.0    | 20.2.0    | 20.2.0    | 20.2.0    | 20.2.0    | 20.2.0    |
| PyHamcrest          | 1.10.1    |           | 1.10.1    |           | 1.10.1    |           |
| Twisted             | 20.3.0    | 21.7.0    | 20.3.0    | 21.7.0    | 20.3.0    | 21.7.0    |
| attrs               | 21.2.0    | 21.2.0    | 21.2.0    | 21.2.0    | 21.2.0    | 21.2.0    |
| autobahn            | 19.11.2   | 21.3.1    | 19.11.2   | 21.3.1    | 19.11.2   | 21.3.1    |
| certifi             | 2021.5.30 | 2021.5.30 | 2021.5.30 | 2021.5.30 | 2021.5.30 | 2021.5.30 |
| cffi                | 1.14.6    | 1.14.6    | 1.14.6    | 1.14.6    | 1.14.6    | 1.14.6    |
| constantly          | 15.1.0    | 15.1.0    | 15.1.0    | 15.1.0    | 15.1.0    | 15.1.0    |
| cryptography        | 3.3.2     | 3.4.8     | 3.3.2     | 3.4.8     | 3.3.2     | 3.4.8     |
| enum34              | 1.1.10    |           | 1.1.10    |           | 1.1.10    |           |
| hyperlink           | 21.0.0    | 21.0.0    | 21.0.0    | 21.0.0    | 21.0.0    | 21.0.0    |
| idna                | 2.10      | 3.2       | 2.10      | 3.2       | 2.10      | 3.2       |
| incremental         | 21.3.0    | 21.3.0    | 21.3.0    | 21.3.0    | 21.3.0    | 21.3.0    |
| ipaddress           | 1.0.23    |           | 1.0.23    |           | 1.0.23    |           |
| pip                 | 20.3.4    | 21.2.4    | 20.3.4    | 21.1.2    |           |           |
| pyOpenSSL           | 20.0.1    | 20.0.1    | 20.0.1    | 20.0.1    | 20.0.1    | 20.0.1    |
| pyasn1              | 0.4.8     | 0.4.8     | 0.4.8     | 0.4.8     | 0.4.8     | 0.4.8     |
| pyasn1-modules      | 0.2.8     | 0.2.8     | 0.2.8     | 0.2.8     | 0.2.8     | 0.2.8     |
| pycparser           | 2.2       | 2.2       | 2.2       | 2.2       | 2.2       | 2.2       |
| service-identity    | 21.1.0    | 21.1.0    | 21.1.0    | 21.1.0    | 21.1.0    | 21.1.0    |
| setuptools          | 44.1.1    | 47.1.0    | 44.1.1    | 57.4.0    |           |           |
| six                 | 1.16.0    | 1.16.0    | 1.16.0    | 1.16.0    | 1.16.0    | 1.16.0    |
| txaio               | 18.8.1    | 21.2.1    | 18.8.1    |           | 18.8.1    | 21.2.1    |
| typing              | 3.10.0.0  |           | 3.10.0.0  | 21.2.1    | 3.10.0.0  |           |
| wheel               | 0.36.2    |           | 0.36.2    | 3.10.0.2  |           |           |
| wsgiref             | 0.1.2     |           |           | 0.37.0    |           |           |
| zope.interface      | 5.4.0     | 5.4.0     | 5.4.0     | 5.4.0     | 5.4.0     | 5.4.0     |
| typing-extensions   |           | 3.10.0.2  |           |           |           | 3.10.0.2  |
| twisted-iocpsupport |           |           |           | 1.0.2     |           |           |

## How to update 3rd party packages for the browser integration

- Update the high-level list of packages to use inside `requirements.txt`
- Run `update_requirements.py`. This will bake the official versions of each
   package we need to install for each platform and in which folder.
- Run `install_source_only.sh`
- Run the `install_binary_*.*` scripts on their respective platform.

# Updating the list of package to use.

The list of top level dependencies is inside `requirements.txt`. Update this list if a security
issue is flagged and a module needs to be updated.

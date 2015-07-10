# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Example command line usages for trial tests

    trial base
    trial base.test_localization
"""

import sys
import os
from optparse import OptionParser
import logging
logging.basicConfig(level=logging.INFO)

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
print "Adding tank location to python_path: %s" % python_path
sys.path = [python_path] + sys.path

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "python"))
print "Adding tests/python location to python_path: %s" % python_path
sys.path = [python_path] + sys.path

from twisted.trial import unittest, runner
from twisted.trial.reporter import *

#
# Unit Test Packages
import tests


class TestRunner(object):
    def __init__(self):
        file_path = os.path.abspath(__file__)
        self.test_path = os.path.dirname(file_path)
        self.packages_path = os.path.join(os.path.dirname(self.test_path), "python")
        sys.path.append(self.packages_path)
        sys.path.append(self.test_path)
        self.suite = None

    def setup_suite(self, test_name):
        loader = runner.TestLoader()

        # args used to specify specific module.TestCase.test
        if test_name:
            self.suite = loader.loadTestsFromName(test_name)
        else:
            # Have not found a proper 'discover'. So need to add test packages by hand here
            self.suite = loader.loadPackage(tests)

    def run_tests(self, test_name, verbose=False):
        if verbose:
            result = VerboseTextReporter()
        else:
            result = Reporter()

        self.setup_suite(test_name)
        self.suite.run(result)

        return result


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--verbose",
                      action="store_true",
                      dest="verbose",
                      help="test reporter verbosity")
    (options, args) = parser.parse_args()

    # Note: name is same format as trial (ie: 'test.test_echo')
    test_name = None
    if args:
        test_name = args[0]

    test_runner = TestRunner()
    result = test_runner.run_tests(test_name, options.verbose)

    # Exit value determined by failures and errors
    exit_val = 0
    if not result.wasSuccessful():
        exit_val = 1

    sys.exit(exit_val)

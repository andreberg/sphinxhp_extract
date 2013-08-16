#!/usr/local/bin/python
# encoding: utf-8
'''
sphinxhp.errors -- error and exception classes used throughout sphinxhp.

:author:    | André Berg
:copyright: | 2011 Berg Media. All rights reserved.
:license:   | Licensed under the Apache License, Version 2.0 (the "License");
            | you may not use this file except in compliance with the License.
            | You may obtain a copy of the License at
            | 
            | http://www.apache.org/licenses/LICENSE-2.0
            | 
            | Unless required by applicable law or agreed to in writing, software
            | distributed under the License is distributed on an **"AS IS"** **BASIS**,
            | **WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied.
            | See the License for the specific language governing permissions and
            | limitations under the License.
:contact:   | andre.bergmedia@googlemail.com
'''

import os

import constants


__version__ = (0, 1)
__versionstr__ = '.'.join([str(num) for num in __version__])
__date__ = constants.__date__
__updated__ = '2013-08-16'

__all__ = ['CLIError', 'InvalidStateError']


DEBUG = 0 or ('BMDebugLevel' in os.environ and os.environ['BMDebugLevel'] > 0)
TESTRUN = 0 or ('BMTestRunLevel' in os.environ and os.environ['BMTestRunLevel'] > 0)
PROFILE = 0 or ('BMProfileLevel' in os.environ and os.environ['BMProfileLevel'] > 0)


class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError, self).__init__()
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg


class InvalidStateError(Exception):
    '''Error to raise if an object is in an invalid state.'''
    def __init__(self, msg):
        super(InvalidStateError, self).__init__()
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

#!/usr/local/bin/python
# encoding: utf-8
#@PydevCodeAnalysisIgnore
# pylint: disable=F0401,W0611,W0622
'''
sphinxhp_extract.compat -- compatibility layer for dual Python integration etc. 

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
import os, sys

__date__ = '2011-10-01'
__updated__ = '2013-07-08'


PY3 = sys.version_info >= (3, 0)

# pylint:disable-msg=F0401, E0611

# Python 3.x is picky about bytes and strings, so provide methods to
# get them right, and make them no-ops in 2.x
if PY3:
    def to_bytes(s):
        """Convert string `s` to bytes."""
        return s.encode('utf8')

    def to_string(b):
        """Convert bytes `b` to a string."""
        return b.decode('utf8')
    
    def write_encoded(fname, text, encoding='utf-8', errors='strict', mode='w'):
        '''Write string `text` to file names `fname`, with encoding.'''
        f = open(fname, mode=mode, encoding=encoding, errors=errors)
        try:
            f.write(text)
        finally:
            f.close()
else:
    def to_bytes(s):
        """Convert string `s` to bytes (no-op in 2.x)."""
        return s

    def to_string(b):
        """Convert bytes `b` to a string (no-op in 2.x)."""
        return b
    
    def write_encoded(fname, text, encoding='utf-8', errors='strict', mode='w'):
        '''Write utf-8 string `text` to file names `fname`, with encoding.'''
        import codecs
        f = codecs.open(fname, mode=mode, encoding=encoding, errors=errors)
        try:
            f.write(text.decode('utf-8'))
        finally:
            f.close()


#!/usr/local/bin/python
# encoding: utf-8
'''
sphinxhp.utils -- there's, uhm, utility stuff in here.

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
import re
import time
import functools
import warnings

# pylint:disable-msg=F0401, E0611
try:
    # Python 3
    import urllib.parse as urlparse
    import urllib.request as urllib 
    import http.client as httplib
except ImportError:
    # Python 2
    import urllib
    import urlparse
    import httplib
# pylint:enable-msg=F0401, E0611

import constants
from compat import write_encoded

from docutils.core import publish_string


__date__ = constants.__date__
__updated__ = '2013-08-16'


DEBUG = 0 or ('BMDebugLevel' in os.environ and os.environ['BMDebugLevel'] > 0)
TESTRUN = 0 or ('BMTestRunLevel' in os.environ and os.environ['BMTestRunLevel'] > 0)
PROFILE = 0 or ('BMProfileLevel' in os.environ and os.environ['BMProfileLevel'] > 0)


def deprecated(level=1, since=None, info=None):
    '''
    This decorator can be used to mark functions as deprecated.
        
    :param level: severity level. 
                  0 = warnings.warn(category=DeprecationWarning)
                  1 = warnings.warn_explicit(category=DeprecationWarning)
                  2 = raise DeprecationWarning()
    :type level: ``int``
    :param since: the version where deprecation was introduced.
    :type since: ``string`` or ``int``
    :param info: additional info. normally used to refer to the new 
                 function now favored in place of the deprecated one.
    :type info: ``string``
    '''
    def __decorate(func):
        if since is None:
            msg = 'Method %s() is deprecated.' % func.__name__
        else:
            msg = 'Method %s() has been deprecated since version %s.' % (func.__name__, str(since))
        if info:
            msg += ' ' + info
        @functools.wraps(func)
        def __wrapped(*args, **kwargs): # IGNORE:C0111
            if level <= 0:
                warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
                func(*args, **kwargs)
            elif level == 1:
                warnings.warn_explicit(msg, category=DeprecationWarning, 
                                       filename=func.__code__.co_filename, 
                                       lineno=func.__code__.co_firstlineno + 1)
            elif level >= 2:
                raise DeprecationWarning(msg)
        return __wrapped
    return __decorate


def create_path(path, mode=0o755):
    '''Create the path incl. intermediary directories using ``os.makedirs``.
    
    Return already existing or newly created ``path``.
    '''
    if os.path.exists(path):
        return path
    else:
        try:
            os.makedirs(path, mode)
            return path
        except Exception as e:
            raise IOError("E: path %r couldn't be created: %s" % (path, e))

    
def isodate_ymd():
    '''%Y-%m-%d -> 2011-10-03'''
    return time.strftime("%Y-%m-%d")


def isodate_full():
    '''%Y-%m-%d %H:%M:%S -> '2011-10-03 23:04:44'''
    return time.strftime("%Y-%m-%d %H:%M:%S")

def now():
    '''Epoch with fractional part'''
    return time.time()


def tstamp():
    '''Epoch time stamp, e.g. 1317676027'''
    return int(now())


def is_local_url(url):
    is_local = False
    result = urlparse.urlsplit(url)
    scheme = result.scheme   # IGNORE:E1103
    if scheme == "file":
        is_local = True
    return is_local


def urlrequest(site, path='', method='HEAD'):
    conn = httplib.HTTPConnection(site)
    if DEBUG: 
        print("_urlrequest: url = http://%s%s" % (site, path))
    conn.request(method, path)
    response = conn.getresponse()
    return response


def write_html(fname, html):
    '''Write `html` to `fname`, properly encoded.'''
    write_encoded(fname, html, 'ascii', 'xmlcharrefreplace')

   
def html_escape(text, convert_spaces=False):
    '''HTML-escape XML special chars (&, ", ', <, >)'''
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;", # coverage.py has &#39; here
        ">": "&gt;",
        "<": "&lt;",
    }
    if convert_spaces:
        result = ''.join(html_escape_table.get(c, c) for c in text)
        return (result
                # Convert runs of spaces: "......" -> "&nbsp;.&nbsp;.&nbsp;."
                .replace("  ", "&nbsp; ")
                # To deal with odd-length runs, convert the final pair of spaces
                # so that "....." -> "&nbsp;.&nbsp;&nbsp;."
                .replace("  ", "&nbsp; "))

    else:
        return "".join(html_escape_table.get(c, c) for c in text)


def url_escape(t):
    return urllib.quote(t)


def linkify(text):
    text = str(text)
    if len(text) == 0:
        return text
    return re.sub(r'((http|https|ftp|file)://.+)', '<a href="\\1">\\2</a>', text, flags=re.UNICODE)


def rst_to_html(text, settings_overrides=None):
    '''Convert reStructuredText to HTML.'''
    if settings_overrides is None:
        settings_overrides = {
            'halt_level': 5,
            'report_level': 5,
            'output_encoding_error_handler': 'xmlcharrefreplace',
            'output_encoding': 'UTF-8'
        }
    return publish_string(text, writer_name='html', settings_overrides=settings_overrides)


def markdown_to_html(text):
    '''Replace common markdown constructs with their HTML counterparts.'''
    result = text.replace('\n', '<br>')
    result = re.sub(r'`{1,2}(.*?)`{1,2}', r'<code>\1</code>', result)
    result = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', result)
    result = re.sub(r'\b[*_](.*?)[*_]\b', r'<i>\1</i>', result)
    result = re.sub(r'\[(.*?)\]\((.*?) (.*?)\)', r'<a href="\2" title="\3">\1</a>', result)
    result = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', result)
    result = re.sub(r'<a href="(.*?)"></a>', r'<a href="\1">\1</a>', result) # fix empty links
    return result


def nl_to_br(text):
    '''Replace occurrences of ``os.linesep`` with ``<br>``.'''
    return text.replace(os.linesep, '<br>')


def printdef(defdict):
    '''
    Print a definition nicely formatted to stdout.
    :param defdict: a dict containing info about the
        definition to print.
    :type defdict: ``dict``
    '''
    template = \
"""
id          : %(id)s
name        : %(name)s
description : %(description)s
since       : %(since)s
deprecated  : %(deprecated)s
permalink   : %(link)s
"""
    sep = "-------------"
    print(sep)
    _template = (template[1:]+sep)
    for entry in defdict:
        print(_template % entry)

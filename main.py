#!/usr/local/bin/python
# encoding: utf-8
# pylint: disable-msg=E1103, E1101
'''
sphinxhp_extract.main -- command line interface.

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
from __future__ import print_function

import sys
import os
import re
import time

# pylint: disable=E0611,F0401
try:
    # Python 3
    from urllib.parse import urlsplit
except ImportError:
    # Python 2
    from urlparse import urlsplit
# pylint: enable=E0611,F0401

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from pprint import pprint

import constants

from data import SphinxDatabase, HTMLWriter, CSVWriter, TextMateWriter, ListWriter
from utils import urlrequest, is_local_url
from errors import CLIError


__all__ = ['main']

__url__ = constants.__url__
__version__ = constants.__version__
__versionstr__ = constants.__versionstr__
__date__ = constants.__date__
__updated__ = '2013-08-16'


DEBUG = 0 or ('BMDebugLevel' in os.environ and os.environ['BMDebugLevel'] > 0)
TESTRUN = 0 or ('BMTestRunLevel' in os.environ and os.environ['BMTestRunLevel'] > 0)
PROFILE = 0 or ('BMProfileLevel' in os.environ and os.environ['BMProfileLevel'] > 0)


# pylint:disable-msg=W0613
def replace_decimal_point(value, *args):
    return re.sub(r'(\d+)\.(\d+)', "\\1,\\2", value)


def to_german_csv(data, *args):
    data = data.replace(",", ";")
    return re.sub(r'(\d+)\.(\d+)', "\\1,\\2", data)


def linkify_tabledata(data, *args):
    return re.sub(r'<td>(http://.*?)</td>', '<td><a href="\\1">\\1</a></td>', data)


def linkify(value, *args):
    return re.sub(r'(http://.*?)', '<a href="\\1">\\1</a>', value)                     
# pylint:enable-msg=W0613


def print_formats():
    print("Valid formats:\n")
    for mode in SphinxDatabase.VALID_FORMATS:
        print("%s" % mode)


def print_epaths(site_url):
    db = SphinxDatabase(site_url)
    db.initialize()
    available_epaths = db.get_epaths()
    print("Available epaths:\n")
    for epath in sorted(available_epaths):
        print(epath)


def main(argv=None):  # IGNORE:C0111
    if isinstance(argv, list):
        sys.argv.extend(argv)
    elif argv is not None:
        sys.argv.append(argv)
            
    program_name = "sphinxhp-data-extractor"  # IGNORE:W0612 @UnusedVariable
    program_version = "v%s" % __versionstr__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = '''%s -- extract Sphinx markup data from the sphinx homepage ''' % program_name
    program_license = u'''%s
    
  Created by André Berg on %s.
  Copyright %s Berg Media. All rights reserved.
  
  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0
  
  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__), time.strftime('%Y'))

    valid_formats = SphinxDatabase.VALID_FORMATS
    
    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument("-l", "--list-epaths", dest="listepaths", action="store_true", help="list element paths available for querying the database and exit")
        parser.add_argument("-o", "--outdir", dest="outdir", help="default output directory. [default: %(default)s]", metavar="path" )
        parser.add_argument("-f", "--force", dest="force", action="store_true", help="force creation of outdir if it doesn't exist. [default: %(default)s]")
        parser.add_argument("-s", "--siteurl", dest="siteurl", help="default url of the Sphinx homepage. can be a local file url [default: %(default)s]", metavar="url" )
        parser.add_argument("-F", "--format", dest="format", help=("output format. One of %r or 'all'. "  % (valid_formats)) + "You can specify multiple formats by separating with a colon, e.g. 'format1:format2' [default: %(default)s]")
        parser.add_argument('-V', '--version', action='version', version=program_version_message)
        parser.add_argument(dest="epaths", help="element paths of the data units to fetch. if None all that is considered 'data' will be emitted by the Database. [default: %(default)s]", metavar="epath", nargs='*')
        
        parser.set_defaults(siteurl=constants.DEFAULT_REMOTE_SITE_URL, outdir=os.curdir, epaths=None, force=False)
        
        parser.prog = program_name

        # Process arguments
        args = parser.parse_args()
        
        listepaths = args.listepaths
        epaths = args.epaths
        verbose = args.verbose
        formatstr = args.format
        siteurl = args.siteurl
        outdir = os.path.realpath(args.outdir)
        force = args.force
        
        db = None
        
        if listepaths:
            print_epaths(siteurl)
            return 0
        
        if formatstr is None:
            formats = ['stdout']
        else:
            if 'all' in formatstr:
                formats = valid_formats
            else:
                formats = formatstr.split(":")
                for format in formats:  # IGNORE:W0622 @ReservedAssignment
                    if format not in valid_formats:
                        raise CLIError("format '%s' not recognized" % format)
        
        if verbose > 0:
            print("Verbose mode on")
            print("format(s): %s" % ', '.join(formats))
            print("url: %s" % siteurl)
            print("outdir: %s" % outdir)
            print("force: %s" % force)
            print("epaths: %s" % epaths)

        try:
            urlcomps = urlsplit(siteurl)
            siteurl_base = urlcomps.netloc
            site_path = urlcomps.path
            if not is_local_url(siteurl):
                response = urlrequest(siteurl_base, site_path)
                if response.status != 200:
                    raise ValueError("E: siteurl may be malformed.")
        except Exception as e:
            raise(e)
        
        if 'stdout' not in formats:
            if not os.path.exists(outdir):
                if force:
                    try:
                        if verbose > 0:
                            print("Creating path to outdir...")
                        os.makedirs(outdir, 0o755)
                    except Exception as e: # IGNORE:W0703
                        CLIError("outdir %r doesn't exist and couldn't be created. An exception occurred: %s" % (outdir, e))
                else:
                    raise CLIError("outdir %r doesn't exist.\nPass -f/--force if you want to have it created anway." % outdir)

 
        if not db:
            db = SphinxDatabase(siteurl)
            if verbose > 0:
                print("Initializing SphinxDatabase %d..." % id(db))
            db.initialize()
        
        for format in formats:  # @ReservedAssignment
            _outdir = os.path.join(outdir, format)
            if format == "html":
                if verbose > 0:
                    print("Writing HTML data to '%s'" % _outdir)
                writer = HTMLWriter(db, _outdir)
                writer.write()
            elif format == 'csv':
                if verbose > 0:
                    print("Writing CSV data to '%s'" % _outdir)
                writer = CSVWriter(db, _outdir)
                # could just specify semicolon as colsep to get CSV seen 
                # valid in German Excel, but we need to convert float values 
                # from 0.n to 0,n as well so we use the callback function
                writer.value_callback = to_german_csv
                writer.write()
            elif format == 'tmprefs':
                if verbose > 0:
                    print("Writing TMPrefs data to '%s'" % _outdir)
                writer = TextMateWriter(db, _outdir)
                writer.write()
            elif format == 'list':
                if verbose > 0:
                    print("Writing List data to '%s'" % outdir)
                writer = ListWriter(db, _outdir)
                writer.write(include_comments=True)
            else: # mode == 'stdout'
                if len(epaths) == 0:
                    db.print_data(func=pprint)
                else:
                    db.print_data(epaths=epaths, func=pprint)
        return 0
    except KeyboardInterrupt:
        if verbose > 0:
            print("Aborted")
        return 0
    except CLIError as e:
        print(e)
        return 1
    except Exception as e:
        if DEBUG or TESTRUN:
            raise(e)
        print(sys.argv[0].split("/")[-1] + ": " + str(e), file=sys.stderr)
        print("\t for help use --help", file=sys.stderr)
        return 2

if __name__ == "__main__":
    '''Command line options.'''  # IGNORE:W0105
    if DEBUG:        
        print(sys.version)
        #sys.argv.append("-l")
        sys.argv.append("-v")
        #sys.argv.append("-h")
        sys.argv.append("-f")
        sys.argv.extend(["-o", "tests/sphinxhp-data"])
        #test_site_url = "file://" + os.path.join(os.path.abspath(os.curdir), "tests", "sphinx_pocoo_org")
        #sys.argv.extend(["--mode=csv:html:tmprefs"])
        sys.argv.extend(["--format=all", 'data/type/*'])
        #sys.argv.extend(["--mode=csv:html:tmprefs", "-s", test_site_url])
        #sys.argv.extend(["-s", test_site_url])
        #sys.argv.extend(["-s", test_site_url, 'data/type/role', 'this/doesnt/exist'])
        #sys.argv.extend(["-s", test_site_url, 'data/type/*'])
    if TESTRUN:
        import doctest
        doctest.testmod()
    if PROFILE:
        import cProfile
        import pstats
        def profile_tasks():
            test_site_url = "file://" + os.path.join(os.path.abspath(os.curdir), "tests", "sphinx_pocoo_org")
            sys.argv.extend(['-v', '-f', '--mode=csv:html', "-s", test_site_url, '-o', 'tests/sphinxhp-data'])
            main()
        profile_filename = 'main-profile.pstats'
        cProfile.run('profile_tasks()', profile_filename)
        statsfile = open("main-profile.pstats.txt", "wb")
        p = pstats.Stats(profile_filename, stream=statsfile)
        stats = p.strip_dirs().sort_stats('cumulative')
        print(stats.print_stats(), file=statsfile)
        statsfile.close()
        sys.exit(0)
    sys.exit(main())
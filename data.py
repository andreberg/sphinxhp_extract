#!/usr/local/bin/python
# encoding: utf-8
# pylint: disable-msg=E1101,C0302
'''
sphinxhp.data -- sphinx homepage data processing utilities 

The data module contains tools for extracting, storing, 
serving and outputting information that can be found by 
parsing the Sphinx homepage.
 
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
import sys
import string  # IGNORE:W0402
import codecs
import shutil


# pylint:disable-msg=F0401, E0611
try:
    # Python 3
    import urllib.parse as urlparse
    import urllib.request as urllib 
    import html.entities as htmlentitydefs
except ImportError:
    # Python 2
    import urllib
    import urlparse
    import htmlentitydefs
# pylint:enable-msg=F0401, E0611


import constants
from compat import write_encoded
from templite import Templite
from utils import (html_escape, url_escape, linkify, rst_to_html, 
                            markdown_to_html, nl_to_br, tstamp, create_path, 
                            urlrequest, deprecated)
from errors import InvalidStateError

_is_lxml = False
try:
    import lxml, lxml.html
    # pylint: disable=E0611,F0401
    from lxml.etree import XMLParser
    _is_lxml = True
    # pylint: enable=E0601,F0401
except ImportError:
    from xml.etree.ElementTree import XMLParser
    import xml.etree.ElementTree as etree


__all__ = ['DataExtractor', 'SphinxDatabase', 'HTMLWriter', 'CSVWriter', 'TextMateWriter']

__date__ = constants.__date__
__updated__ = '2013-08-20'


DEBUG = 0 or ('BMDebugLevel' in os.environ and os.environ['BMDebugLevel'] > 0)
TESTRUN = 0 or ('BMTestRunLevel' in os.environ and os.environ['BMTestRunLevel'] > 0)
PROFILE = 0 or ('BMProfileLevel' in os.environ and os.environ['BMProfileLevel'] > 0)


def check_database(database):
    '''Check if the database is not None and initalized.
    
    Calls `<database.initialize()>`_ if the database 
    hasn't been initialized yet and ``initialize`` is True.
    '''
    if database is None:
        raise ValueError("database is None.")
    elif not database.initialized:
        raise ValueError("database is not initialized.")
    return database


def _data(fname):
    '''Return the contents of a data file of ours.'''
    data_file = open(_data_filename(fname))
    try:
        return data_file.read()
    finally:
        data_file.close()


def _data_filename(fname):
    '''Return the path to a data file of ours.'''
    return os.path.join(os.path.split(__file__)[0], fname)


class Writer(object):
    '''Base class for all writers.'''
    
    def __init__(self, database, outdir): # IGNORE:W0621
        super(Writer, self).__init__()
        self.database = check_database(database)
        self.outdir = create_path(os.path.realpath(outdir))
        
    def write(self, *args, **kwargs):
        raise NotImplementedError('Write.write() is abstract for %s' % type(self))


class TextMateWriter(Writer):
    '''
    Output the data stored in `SphinxDatabase` as string array 
    suitable for pasting into ``tmPreferences`` completion-list files.
    
    Example output::
        
        <string>word1</string> <!-- word1 comment -->
        <string>word2</string> <!-- word2 comment -->
    '''
    
    def __init__(self, database, outdir):  # IGNORE:W0621
        super(TextMateWriter, self).__init__(database, outdir)
        self.encoding = sys.getdefaultencoding()
    
    def write(self, epaths=None):  # IGNORE:W0221
        def __append_entries(entries, settings):
            lines = []
            descriptions = []
            result = []
            # split on first period, but ignore 'e.g.' and 'etc.'
            desc_first_line_re = re.compile(r'(?<!e|g|c)\.', re.IGNORECASE | re.UNICODE)
            key, search_regex, repl_regex = settings
            for entry in entries:
                desc = entry['description']
                if len(desc) > 0:
                    desc = re.sub(r'[\r\n]', ' ', re.split(desc_first_line_re, desc, 2)[0])
                else:
                    desc = 'no description'
                try:
                    name = re.sub(search_regex, repl_regex, entry[key], re.IGNORECASE)
                    name = name.split(':')[-1]
                    lines.append(str_template % (indent, name))
                    descriptions.append(cmt_template % desc)
                except Exception as e: # IGNORE:W0703
                    if DEBUG:
                        print('Exception: %s' % e)
                    continue
            max_pos = len(max(lines, key=len))
            for i, line in enumerate(lines):
                result.append(line + '  ' + (' ' * (max_pos - len(line))) + descriptions[i])
            return result
        
        value_settings = {
            'data/type/role':      ('name', r':(.+):',                 r'\1'),
            'data/type/directive': ('name', r'\.\. (.+)::',            r'\1'),
            'data/type/describe':  ('name', r'(\|(.+)\||\.\. (.+)::)', r'\1'),
            'data/type/confval':   ('name', r':(.+):',                 r'\1'),
            'data/type/function':  ('name', r'(.+)(?:\(.*\))?',        r'\1')
        }
        default_settings = ('name', r'(.+)', r'\1')
            
        # need to handle each type seperatly because we need to extract
        # strings differently from the ids and names. this is also why
        # we don't support caller giving a target epath.
        fext = '.txt'
        indent = '    ' * 3
        str_template = '%s<string>%s</string>'
        cmt_template = '<!-- %s -->'
        if not epaths:
            epaths = self.database.expand_epath('data*')
        num_written_files = 0
        for epath in epaths:
            settings = value_settings.get(epath, default_settings)
            cur_data = self.database.get_data(epath)
            comps = epath.split('/')[1:]
            cur_fname = '-'.join(comps) + fext
            cur_lines = __append_entries(cur_data, settings)
            write_encoded(os.path.join(self.outdir, cur_fname), 
                          os.linesep.join(cur_lines), encoding=self.encoding, errors="strict")
            num_written_files += 1
        return num_written_files


class ListWriter(Writer):
    '''
    Output the data stored in `SphinxDatabase` as string representing
    a list like syntax in a language like Ruby or Python.   
    
    Mainly for the ``Completions for Word.tmCommand``.
    
    Example output::
        
        ['word1', ... 'wordN']
    '''
    
    def __init__(self, database, outdir):  # IGNORE:W0621
        super(ListWriter, self).__init__(database, outdir)
        self.encoding = sys.getdefaultencoding()
    
    def write(self, epaths=None, include_comments=False):  # IGNORE:W0221
        def __append_entries(entries, settings):
            lines = []
            descriptions = []
            result = []
            # split on first period, but ignore 'e.g.' and 'etc.'
            desc_first_line_re = re.compile(r'(?<!e|g|c)\.', re.IGNORECASE | re.UNICODE)
            key, search_regex, repl_regex = settings
            for entry in entries:
                desc = entry['description']
                if len(desc) > 0:
                    desc = re.sub(r'[\r\n]', ' ', re.split(desc_first_line_re, desc, 2)[0])
                else:
                    desc = 'no description'
                try:
                    name = re.sub(search_regex, repl_regex, entry[key], re.IGNORECASE)
                    name = name.split(':')[-1]
                    lines.append(str_template % (indent, name))
                    descriptions.append(cmt_template % desc)
                except Exception as e: # IGNORE:W0703
                    if DEBUG:
                        print('Exception: %s' % e)
                    continue
            max_pos = len(max(lines, key=len))
            if include_comments is True:
                for i, line in enumerate(lines):
                    result.append(line + '  ' + (' ' * (max_pos - len(line))) + descriptions[i])
            else:
                result = lines
            return result
        
        value_settings = {
            'data/type/role':      ('name', r':(.+):',                 r'\1'),
            'data/type/directive': ('name', r'\.\. (.+)::',            r'\1'),
            'data/type/describe':  ('name', r'(\|(.+)\||\.\. (.+)::)', r'\1'),
            'data/type/confval':   ('name', r':(.+):',                 r'\1'),
            'data/type/function':  ('name', r'(.+)(?:\(.*\))?',        r'\1')
        }
        
        default_settings = ('name', r'(.+)', r'\1')
            
        # need to handle each type seperatly because we need to extract
        # strings differently from the ids and names. this is also why
        # we don't support caller giving a target epath.
        fext = '.txt'
        if include_comments is True:
            indent = '   '
        else:
            indent = ''
        str_template = '%s"%s", '
        cmt_template = ' # %s'
        if not epaths:
            epaths = self.database.expand_epath('data*')
        num_written_files = 0
        for epath in epaths:
            settings = value_settings.get(epath, default_settings)
            cur_data = self.database.get_data(epath)
            comps = epath.split('/')[1:]
            cur_fname = '-'.join(comps) + fext
            cur_lines = __append_entries(cur_data, settings)
            if include_comments is True:
                final_lines = "[" + os.linesep + (os.linesep.join(cur_lines)) + os.linesep + "]"
            else:
                cur_lines[-1] = cur_lines[-1][:-2]  # remove ', ' from last entry
                final_lines = "[" + (''.join(cur_lines)) + "]"
            write_encoded(os.path.join(self.outdir, cur_fname), 
                          final_lines, encoding=self.encoding, errors="strict")
            num_written_files += 1
        return num_written_files


class CSVWriter(Writer):
    '''Output the data stored in `SphinxDatabase` as comma separated value files.'''
 
    def __init__(self, database, outdir):  # IGNORE:W0621
        super(CSVWriter, self).__init__(database, outdir)
        self.colsep = ","
        self.rowsep = os.linesep
        self.empty_value = ''
        self.value_callback = None
        self.encoding = sys.getdefaultencoding()
        self._header = ['name', 'value']
        self._num_written_files = 0

    def _sanitize_data(self, value):
        value = value.replace('"', '""')
        #value = value.replace('\n', r'\n')
        #value = value.replace('\r', r'\r')
        #value = value.replace('\t', r'\t')
        value = '"' + value + '"'
        return value

    def _sanitize_epaths(self, epaths, primary_type):
        for epath in epaths:
            if self.database.primary_type(epath) != primary_type:
                raise ValueError('E: epath must begin with "%s/..."' % primary_type)
    
    def _data_to_csv(self, epath):
        data = self.database.get_data(epath)  # IGNORE:W0621
        if data is None:
            data = self.empty_value
        result = []
        if not isinstance(data, list):
            comps = epath.split('/')[1:]
            name = " » ".join(comps).replace("_", " ")
            value = linkify(str(data))
            curdata = "%s%s%s" % (name, self.colsep, value)
            result.append(curdata)
        else:
            if len(data) == 0:
                return self.empty_value
            # get column names from the first dict in the data list
            # this assumes that each item's dict has the same layout
            # which should always be true considering how this database
            # is constructed
            rows = []
            columns = list(data[0].keys())
            self._header = columns
            curdata = self.colsep.join(columns)
            rows.append(curdata)
            for item in data:
                curdata = ''
                for column in columns:
                    value = item[column]
                    if not value:
                        value = self.empty_value
                    value = self._sanitize_data(value)
                    curdata += value + self.colsep
                curdata = curdata[:-1]  # remove trailing colsep
                rows.append(curdata)
            result = rows
        return result
    
    def _do_value_callback(self, rows):
        if self.value_callback is None:
            return rows
        for idx, value in enumerate(rows):
            modified_value = self.value_callback(value, idx, self._header)  # IGNORE:E1102
            rows[idx] = modified_value
        return rows
        
    def _handle_metadata(self, epath=None):
        primary_type = 'metadata'
        fullpath = os.path.join(self.outdir, primary_type + '.csv')
        header = "%s%s" % (self.colsep.join(self._header), self.rowsep)
        rows = [header]
        if epath is None:
            epaths = self.database.expand_epath(primary_type + '*')
        else:
            epaths = self.database.expand_epath(epath)
        try:
            self._sanitize_epaths(epaths, primary_type)
        except ValueError:
            return
        for epath in epaths:
            rest = self._data_to_csv(epath)
            rest = self._do_value_callback(rest)
            rows.extend(rest)
        csvdata = self.rowsep.join(rows)
        write_encoded(fullpath, csvdata, encoding=self.encoding, errors='xmlcharrefreplace')
        self._num_written_files += 1

    def _handle_data(self, epath=None):
        primary_type = 'data'
        if epath is None:
            epaths = self.database.expand_epath(primary_type + '*')
        else:
            epaths = self.database.expand_epath(epath)
        try:
            self._sanitize_epaths(epaths, primary_type)
        except ValueError:
            return
        for epath in epaths:
            rows = self._data_to_csv(epath)
            if (len(rows) == 0):
                continue
            rows = self._do_value_callback(rows)
            csvdata = self.rowsep.join(rows)
            comps = epath.split("/")[1:]
            if len(comps) == 1:
                fullpath = os.path.join(self.outdir, comps[0])
            else:
                fullpath = os.path.join(self.outdir, comps[0] + "-" + comps[1])
            fullpath += ".csv"
            write_encoded(fullpath, csvdata, encoding=self.encoding, errors='xmlcharrefreplace')
            self._num_written_files += 1
            
    def write(self, epaths=None):  # IGNORE:W0221
        if epaths is None:
            epaths = self.database.get_epaths()
        for epath in epaths:
            self._handle_metadata(epath)
            self._handle_data(epath)
        return self._num_written_files


class HTMLWriter(Writer):
    '''Output the data stored in the `SphinxDatabase` as HTML files.'''
    # HTMLWriter is adopted from coverage.py's HTMLReport
    
    # These files will be copied from the htmlfiles dir to the output dir.
    STATIC_FILES = [
        "style.css",
        "jquery-1.4.3.min.js",
        "jquery.hotkeys.js",
        "jquery.isonscreen.js",
        "jquery.tablesorter.js",
        "scripts.js",
        "keybd_closed.png",
        "keybd_open.png"
    ]

    def __init__(self, database, outdir): # IGNORE:W0621
        super(HTMLWriter, self).__init__(database, outdir)
        self.data_units = []
        self.template_globals = {
            'escape': html_escape,
            'html_escape': html_escape,
            'url_escape': url_escape,
            'linkify': linkify,
            'rst_to_html': rst_to_html,
            'nl_to_br': nl_to_br,
            'markup_to_html': markdown_to_html,
            'sphinx_version': self.database.get_data("metadata/sphinx/version"),
            '__url__': constants.__url__,
            '__version__': constants.__versionstr__  # yes, versionstr not version!
        }
        self.data_tmpl = Templite(_data("htmlfiles/data.html"), self.template_globals)
        self.metadata_tmpl = Templite(_data("htmlfiles/metadata.html"), self.template_globals)

    def _copy_static_files(self):
        '''Copy static files for HTML report.'''
        for static in self.STATIC_FILES:
            shutil.copyfile(_data_filename("htmlfiles/" + static), 
                            os.path.join(self.outdir, static))
        return len(self.STATIC_FILES)
                
    def _write_index_file(self):
        '''Write the index.html file for this report.'''
        index_tmpl = Templite(_data("htmlfiles/index.html"), self.template_globals)
        data_units = self.data_units    # IGNORE:W0612
        total_entries = 0               # IGNORE:W0612
        for unit in self.data_units:
            total_entries += unit.num_entries
        self._write_html(os.path.join(self.outdir, "index.html"),
                         index_tmpl.render(locals()))
        
    def _write_file(self, entries, du, filetype='data'):
        '''Generate HTML file for data unit (du).'''
        unit_name = du.name     # IGNORE:W0612
        if DEBUG:
            print("entries = %r" % entries)
            print("out_path = %r" % du.file_abspath)
            print("data unit = %r" % du)
            #print("len(entries) = %r" % len(entries))
            #print("du.num_entries = %r" % du.num_entries) 
        try:
            self.data_units.append(du)
            if filetype == 'data':
                html = self.data_tmpl.render(locals())
            elif filetype == 'metadata':
                html = self.metadata_tmpl.render(locals())
            else:
                raise ValueError("unknown template file type: '%s'" % filetype)
            self._write_html(du.file_abspath, html)
            return True
        except Exception as e:    # IGNORE:W0703
            if DEBUG: 
                raise(e) 
            return False
        
    def _write_html(self, fname, html):
        '''Write `html` to `fname`, properly encoded.'''
        write_encoded(fname, html, encoding='ascii', errors='xmlcharrefreplace')
        
    def write(self, epaths=None): # IGNORE:W0221
        num_written_files = 0
        if epaths:
            if not isinstance(epaths, list):
                epaths = [epaths]
        else:
            epaths = self.database.get_epaths()
        if not epaths:
            raise ValueError("E: no data to write")
        
        data_epaths = self.database.expand_epath('data*')
        metadata_epaths = self.database.expand_epath('metadata*')
        
        # consolidate metadata
        consolidated_metadata = []
        for epath in metadata_epaths:
            value = self.database.get_data(epath)
            if not value or len(str(value)) == 0:
                continue
            comps = epath.split('/')[1:]
            consolidated_metadata.append({
                'name': " » ".join(comps).replace("_", " "), 
                'value': linkify(value)
            })
            
        # set local variables for template
        # pylint: disable-msg=W0612
        unit_name = "Metadata"
        unit_num_entries = len(consolidated_metadata)
        # pylint: enable-msg=W0612
        out_filename = "metadata.html"
        out_path = os.path.join(self.outdir, out_filename)
        
        du = DataUnit(file_relpath=os.path.relpath(out_path, self.outdir), 
                      file_abspath=os.path.abspath(out_path),
                      basename=out_filename, 
                      num_entries=unit_num_entries, 
                      name=unit_name)
        
        num_written_files += self._write_file(consolidated_metadata, du, filetype='metadata')
                            
        for epath in data_epaths: 
            cur_data = self.database.get_data(epath)
            if not cur_data or len(str(cur_data)) == 0:
                continue
            if not isinstance(cur_data, list):
                cur_data = [cur_data]

            comps = epath.split('/')[1:]
            # set local variables for template
            # pylint: disable-msg=W0612
            unit_name = string.capwords(' '.join(comps))
            unit_num_entries = len(cur_data)
            # pylint: enable-msg=W0612
            
            out_filename = '-'.join(comps) + ".html"
            out_path = os.path.join(self.outdir, out_filename)
            
            du = DataUnit(file_relpath=os.path.relpath(out_path, self.outdir), 
                          file_abspath=os.path.abspath(out_path),
                          basename=out_filename, 
                          num_entries=unit_num_entries, 
                          name=unit_name)
            
            num_written_files += self._write_file(cur_data, du, filetype='data')
        
        self._write_index_file()
        num_written_files += 1
        num_copied = self._copy_static_files()
        num_written_files += num_copied
        
        return num_written_files


class DataExtractor(object):
    '''
    DataExtractor is the class that is in charge of knowing 
    how to extract data from the Sphinx homepage. 
    
    It exposes a method for each I{thing} to extract and 
    stores the result of the extraction in C{self.contents}.
    
    This also means DataExtractor instances are usually
    instantiated for one purpose each.
    '''

    SINCE_REGEX = re.compile(r'New in version (?P<version>\d+\.\d+)', re.IGNORECASE)
    DEPRECATED_REGEX = re.compile(r'Deprecated since version (\d+\.\d+)', re.IGNORECASE)
    VERSION_REGEX = re.compile(r'VERSION:\s*[\"\']{0,1}(.+?)[\"\']{0,1},', re.IGNORECASE)
    DL_XPATH = ".//div[@class='section']/dl"
    
    def __init__(self, url):
        super(DataExtractor, self).__init__()
        self.url = url
        is_local = True
        try:
            result = urlparse.urlsplit(url)
            site = result.netloc   # IGNORE:E1103
            path = result.path     # IGNORE:E1103
            scheme = result.scheme # IGNORE:E1103
            # check if site exists
            if not scheme == "file":
                is_local = False
                # but only if we do not operate locally
                response = urlrequest(site, path)
                if response.status != 200:
                    raise ValueError("Status %d (%s)" % (response.status, response.reason))
        except Exception as e: # IGNORE:W0703
            print("E: accessing site '%s' returned '%s'" % (site, e))
        self.site = result.netloc   # IGNORE:E1103
        self.path = result.path     # IGNORE:E1103
        self.is_local = is_local
        self.source = None
        self.type = None
        self.xpath = self.DL_XPATH
        self.encoding = sys.getdefaultencoding()
        
    def __str__(self):
        return "%s url: %s, type: %s" % (super(DataExtractor, self).__repr__(), self.url, self.type)
    
    def __repr__(self):
        return "DataExtractor(%s)" % str(self.url)
        
    def _read(self, url=None):
        source = None
        if url is None:
            url = self.url
        try:
            if DEBUG: 
                print("_read url '%s'" % url)
            f = urllib.urlopen(url)
            try:
                source = f.read()
            finally:
                f.close()
        except Exception as e: # IGNORE:W0703
            raise IOError("E: couldn't read resource at '%s'. The error msg was: %s" % (self.url, e))
        return source.decode(self.encoding)

    def get_sphinx_version(self, path="/index.html", regex=None):
        ''' Get the version of Sphinx used for the documentation at self.url.
        
        @param path: path to the resource relative to I{self.url}.
        @param regex: regex to use for extraction. must have 1 group 
            which matches the version portion of the string.
            default: L{DataExtractor.VERSION_REGEX}
        @type regex: regex string or regex object
        @return: extracted version string
        '''
        if not regex:
            regex = DataExtractor.VERSION_REGEX
        version = None
        start_page_url = self.url + path
        page_source = self._read(start_page_url)
        if not page_source:
            return None
        mat = re.search(regex, page_source)
        if mat:
            version = mat.group(1)
        return version

    def get_defs(self):
        def __setup_tree():
            entity_errors = 'skip'
            if _is_lxml: # use lxml
                root = lxml.html.fromstring(self.source)
            else:  # use builtin etree
                if entity_errors == 'replace':
                    # preprocess entities outside of the XML safezone
                    for match in re.finditer(r'&(.+?);', self.source, re.UNICODE):
                        if match.group(1):
                            name = match.group(1)
                            if name in ['gt', 'lt', 'apos', 'amp', 'quot', '#39']: # allowed xml entities
                                continue
                            elif name in htmlentitydefs.name2codepoint:
                                srch = match.group(0)
                                repl = chr(htmlentitydefs.name2codepoint[name])
                                print("Replacing '%s' with '%s'" % (srch, repl))
                                self.source = re.sub(srch, repl, self.source, re.UNICODE)
                else: # 'skip'
                    class AllEntities(object):
                        def __getitem__(self, key):
                            if DEBUG: 
                                print("Replacing entity '%s' with '%s'" % (key, key))
                            return key
                        
                    parser = XMLParser()
                    parser.parser.UseForeignDTD(True)
                    parser.entity = AllEntities()
                    
                root = etree.fromstring(self.source, parser)
                
                # normalize
                xhtmlns = "{http://www.w3.org/1999/xhtml}"
                for elem in root.iter():
                    if elem.tag.startswith(xhtmlns):
                        elem.tag = elem.tag[len(xhtmlns):]
            return root
        
        if not self.source:
            self.source = self._read()
            if not self.source:
                raise ValueError("E: reading the page source failed.")
            
        root = __setup_tree()
        entries = {}
        last_link = ''
        
        dls = root.findall(self.xpath)
        for dl in dls:
            dl_class = dl.get('class')
            dts = dl.findall('./dt')
            dtslen = len(dts)
            if dtslen > 1:
                # construct a 'see <name of last dt>' hint
                # for sections that have a singular description
                # for multiple definitions
                last_dt = dts[-1]
                last_dt_tt_name = last_dt.findtext('./tt')
                desc = 'see %s' % str(last_dt_tt_name)
            for i in range(0, dtslen):
                dt = dts[i]
                dt_id = dt.get('id')
                tts = dt.findall('./tt')
                tt_name = ''
                tt_classname = ''
                for tt in tts:
                    tt_class = tt.get('class')
                    if tt_class == 'descname':
                        tt_name = tt.findtext(".[@class='%s']" % tt_class)
                    elif tt_class == 'descclassname':
                        tt_classname = tt.findtext(".[@class='%s']" % tt_class)
                dt_link = dt.find('./a')
                if dt_link is not None:
                    dt_link = self.url + dt_link.get('href')
                    last_link = dt_link
                else:
                    # use last link found for dl's that 
                    # don't have an anchored href
                    dt_link = last_link
                depr = ''
                since = '0.1'
                if i == dtslen-1:
                    # assemble description for the last dt
                    # since the docs sometimes include only
                    # one description for a bunch of directives,
                    # roles, etc...
                    dd = dl.find('./dd')
                    desc = ''
                    if dd is not None:
                        for sub in dd.itertext():
                            if sub is not None:
                                desc += sub
                mat = re.search(DataExtractor.SINCE_REGEX, desc)
                if mat:
                    since = mat.groupdict()['version']
                mat = re.search(DataExtractor.DEPRECATED_REGEX, desc)
                if mat: 
                    depr = mat.group(1)
                entry = Entry({
                    'id': dt_id,
                    'name': tt_name,
                    'classname': tt_classname,
                    'description': desc,
                    'since': since,
                    'deprecated': depr,
                    'link': dt_link
                }, 'id')

                if dl_class in entries:
                    entries[dl_class].append(entry)
                else:
                    entries[dl_class] = [entry]
                if DEBUG:
                    print(entry)
        return entries
        


class DataUnit(object):
    '''A DataUnit encapsulates information about each data element to be output.'''
    def __init__(self, **kwargs):
        super(DataUnit, self).__init__()
        for key, value in list(kwargs.items()):
            if value is not None:
                setattr(self, key, value)


__entry_classcache__ = {}


class Entry(object):
    '''Represents one entry in the database.
    
    Each entry associates a C{primary_key} and 
    an C{items} dict.
    
    Sequence or iterator interface methods
    are delegated to the items dict, with
    one notable difference:
    
    Comparisons are done on the value returned 
    by C{items[primary_key]}, that is, two 
    instances are considered the same when 
    the value associated with the primary key 
    is the same as the one associated to the 
    primary key of the other instance.
    
    Entry also implements the Flyweight pattern, 
    so that only one instance is created per 
    primary key.
    '''    
    def __new__(cls, items, primary_type):
        obj = __entry_classcache__.get(items[primary_type], None)
        if obj is None:
            return super(Entry, cls).__new__(cls)
        else:
            return obj
    
    def __init__(self, items, primary_type):
        if hasattr(self, 'items'):
            if DEBUG:
                print(("Using object %r from entry classcache." % self))
            return
        super(Entry, self).__init__()
        self.primary_type = primary_type
        self.items = items
        __entry_classcache__[primary_type] = self

    def __getitem__(self, key):
        return self.items[key]
        
    def __iter__(self):
        return iter(self.items)

    def __reversed__(self):
        return reversed(list(self.items.keys()))
        
    def __len__(self):
        return len(self.items)
        
    def __str__(self):
        return '%s %s = %r' % (super(Entry, self).__str__(), 
                               self.primary_type, self.items[self.primary_type])
    
    def __repr__(self):
        return repr(self.items)
    
    def __hash__(self):
        return hash(self.items[self.primary_type])
        
    def __eq__(self, other):
        return self.items[self.primary_type] == other[self.primary_type]
    
    def keys(self):
        return list(self.items.keys())
        
    def values(self):
        return list(self.items.values())


__db_classcache__ = {}


class Database(object):
    ''' Base class for a simple database.
    
    Database is simple in that it manages its
    entries by means of storing them in an
    ordinary dictionary and provides part
    of the usual dict interface methods to
    interact with the underlying entries. 
    
    The entries are keyed by so-called I{element 
    paths} (I{epaths} for short) which are simple
    strings that provide contextual meaning in
    the caller's domain, e.g. the database might 
    not care that some element paths begin with 
    'data' and others 'begin with 'metadata', 
    but to the user of the class it provides the
    means to tell different data apart without 
    actually looking and searching through the 
    data. The semantics are relayed to the caller
    domain while the syntax (e.g. plain old dict 
    access) is utilized within the class domain.
    
    Database can therefore be used like dicts
    (for the most part - see implementation for 
    details).
    
    Database implements the I{Flyweight} pattern, 
    so that only one instance is created per 
    per C{site_url}.
    '''
    
    def __new__(cls, site_url=constants.DEFAULT_REMOTE_SITE_URL, use_cached=True):
        obj = __db_classcache__.get(site_url, None)
        if obj is None or use_cached is False:
            return super(Database, cls).__new__(cls)
        else:
            return obj
 
    def __init__(self, site_url=constants.DEFAULT_REMOTE_SITE_URL, *args, **kwargs):  # IGNORE:W0613
        if (hasattr(self, 'initialized') and 
            getattr(self, 'initialized') is True):
            if DEBUG:
                print(("Using object %r from db classcache." % self))
            return
        super(Database, self).__init__()
        self.site_url = site_url
        self.contents = {}
        self.epaths = {}
        self.total_entries = -1
        self.initialized = False
        __db_classcache__[site_url] = self
    
    def __getitem__(self, key):
        if key in self.contents:
            return self.contents[key]
        else:
            raise KeyError("E: element '%s' doesn't exist" % key)
    
    def __setitem__(self, key, value):
        # maybe make this immutable so that self.contents must 
        # actually be referenced when setting something... 
        # makes it more obvious if used outside the module 
        # or class even
        self.contents[key] = value

    def __len__(self):
        result = -1
        for itm in self.contents:
            result += len(itm)
        return result
    
    def __repr__(self):
        return repr(self.contents)

    def __iter__(self):
        return iter(self.contents)

    def __reversed__(self):
        return reversed(list(self.contents.keys()))

    def __eq__(self, other):
        # this is almost superfluous because as 
        # Database implements the Flyweight pattern
        # there shouldn't be two objects with the
        # same site_url in the first place.
        return self.site_url == other.site_url
        
    def has_key(self, key):
        return key in self.contents
    
    def keys(self):
        return list(self.contents.keys())
    
    def values(self):
        return list(self.contents.values())
    
    def items(self):
        return list(self.contents.items())
    
    def get_data(self, epath):
        raise NotImplementedError("E: method is abstract and intended to be overridden by subclasses")


class SphinxDatabase(Database):
    ''' 
    Encapsulates information about types and 
    syntax found in the Sphinx documentation.
    '''
    
    REGISTRY = {
        'links': [
            'config.html', 
            'domains.html', 
            'builders.html',
            'markup/inline.html', 
            'markup/toctree.html',
            'markup/para.html',
            'markup/code.html',
            'ext/api.html',
            'ext/appapi.html',
            'ext/autodoc.html',
            'ext/autosummary.html',
            'ext/builderapi.html',
            'ext/coverage.html',
            'ext/doctest.html',
            'ext/extlinks.html',
            'ext/graphviz.html',
            'ext/ifconfig.html',
            'ext/inheritance.html',
            'ext/intersphinx.html',
            'ext/math.html',
            'ext/oldcmarkup.html',
            'ext/refcounting.html',
            'ext/todo.html',
            'ext/tutorial.html',
            'ext/viewcode.html',
            'templating.html'
        ]
    }
    
    VALID_FORMATS = ['csv', 'html', 'tmprefs', 'list', 'listplain'] 
    
    def primary_type(self, epath):
        ''' Return the primary type for the given epath.'''
        return epath.split("/")[0] 
        
    def initialize(self):
        '''
        Initialize the database. This sources all site paths specified by 
        SphinxDatabase.REGISTRY['links'] and extracts data using DataExtrator 
        instances.
        '''
        if not self.initialized:
            if DEBUG: 
                print(("Initializing SphinxDatabase %d... from URL %s" % (id(SphinxDatabase), self.site_url)))
            # acquire metadata
            mde = DataExtractor(self.site_url)
            start_page_path = '/index.html'
            res_url = self.site_url + start_page_path
            parsed_version = mde.get_sphinx_version(path=start_page_path)
            self['metadata/sphinx/site_url'] = res_url
            self['metadata/sphinx/version'] = parsed_version
            self.total_entries = 2
            links = SphinxDatabase.REGISTRY['links']
            try:
                for link in links:
                    url = self.site_url + '/' + link
                    de = DataExtractor(url)
                    defs = de.get_defs()
                    for _def in defs:
                        _entries = defs[_def]
                        _key = 'data/type/' + _def
                        if _key in self:
                            cur_entries = self[_key]
                            #print "type(cur_entries) = %s" % type(cur_entries)
                            #print "type(_entries) = %s" % type(_entries)
                            unique_entries = []
                            for _e in _entries:
                                if _e not in cur_entries:
                                    unique_entries.append(_e)
                            self[_key] += unique_entries
                            self.total_entries += len(unique_entries)
                        else:
                            self[_key] = _entries
                            self.total_entries += len(_entries)
            except KeyError:
                if DEBUG: 
                    # no links stored - pass
                    print("skipping processing of links because there are no entries for the current key in the link epaths")
            self.total_entries += 1  # last settattr
            if DEBUG: 
                print("total_entries = %s" % self.total_entries)
            self['metadata/stats/total_entries'] = self.total_entries
            self.epaths = list(self.keys())
            self.initialized = True

    def expand_epath(self, epath):
        result = []
        if '*' in epath or '?' in epath:
            filtered_epaths = []
            epaths = self.get_epaths()
            for ep in epaths:
                pat = re.compile(epath.replace('?', '.').replace('*', '.*?'), re.IGNORECASE)
                if re.match(pat, ep):
                    filtered_epaths.append(ep)
            result = filtered_epaths
        else:
            # nothing to expand... do a basic check
            # if the epath is valid then return it
            if epath in self.get_epaths():
                result = [epath]
            else:
                raise ValueError("E: element at epath doesn't exist")
        return result
    
#     def get_metadata(self, value):
#         return self.get_data('metadata*')
        
    def get_data(self, epath=None):
        ''' Return a dict mapping the current data.

        @param epath: if None, return the complete set,
            else just the subset given by the element 
            path. get_data has limited support for the
            following wildcards: '*' and '?'.
            For example, 'data/*' returns the data for 
            every epath that begins with 'data/', while
            'data/type/rol?' returns data for epaths that
            have an arbitrary character at the last pos. 
        @type epath: C{string}
        '''
        if not isinstance(epath, str):
            raise TypeError('epath is not a string')
        if epath is None:
            result = []
            # get all entries whose primary type is "data"
            epaths = self.get_epaths()
            for epath in epaths:
                result.append(self[epath])
        else:
            result = []
            filtered_epaths = self.expand_epath(epath)
            if len(filtered_epaths) > 1:
                for fe in filtered_epaths:
                    try:
                        cur_data = self[fe]
                        if isinstance(cur_data, list):
                            result.extend(cur_data)
                        else:
                            result.append(cur_data)
                    except KeyError:
                        result.append(None)
            else:
                try:
                    result = self.contents[epath]
                except KeyError:
                    return None
        return result
        
    def get_contents(self):
        '''Return a dict mapping the current data incl. metadata.'''
        return self.contents

    def print_data(self, epaths=None, func=None):
        ''' Print current data to stdout.
        
        @param epath: if None, print the complete set,
            else just the subset given by the element 
            path.
        @type epath: C{string}
        @param func: printing function to use instead 
            of C{print}, e.g. C{pprint.pprint}
        @type func: C{function}
        '''
        def __print(this_data):
            if func is None:
                print(this_data)
            else:
                func(this_data)
        if isinstance(epaths, list):
            for epath in epaths:
                self.print_data(epath, func)
        elif epaths is None:
            curdata = self.get_contents()
            __print(curdata)
        else:
            if isinstance(epaths, list):
                for epath in epaths:
                    curdata = self.get_data(epath)
                    __print(curdata)
            else:
                epath = epaths
                curdata = self.get_data(epath)
                __print(curdata)
        
    def get_epaths(self):
        ''' Return element paths available, based on data present. 
        
        If ``include_all`` is False, return only epaths for elements 
        whose primary type is *data*, otherwise return all data incl. 
        *metadata*.
        '''
        if not self.initialized:
            raise InvalidStateError("Database must be initialize'd before calling get_epaths()")
        return self.epaths
                
    def write(self, outdir, format, epaths=None, timestamp=False):  # IGNORE:W0622 @ReservedAssignment
        '''
        Write current data to a file at path adapted from 
        C{outdir/<date>/<timestamp>/<primary>-<secondary>.<dataformat>}.
        
        Note: C{data_callback} is no longer supported in this version of C{write()}.
        Use one of the C{Writer} classes instead, and set its C{value_callback} ivar
        to the name of your callback method. Currently only C{CSVWriter} supports this,
        although this may change in the future.
               
        @param format: data format. One of C{['csv', 'html', tmprefs']}.
        @type format: C{string}
        @param epaths: list of epaths to write data for.
        @type epaths: C{list<string>}
        @param timestamp: if False, the path mask above becomes
            C{outdir/<date>/<primary>-<secondar>.<syntax>}.
            Warning: existing files may be overwritten when False.
        @type timestamp: C{bool}
        @return: number of files written
        @rtype: C{int}
        '''
        if not self.initialized:
            raise InvalidStateError("Database must be initialize'd before calling write()")
        if timestamp:
            outdir = os.path.join(outdir, str(tstamp()))
        outdir = create_path(outdir)
        if format is 'csv':
            writer = CSVWriter(self, outdir)
        elif format is 'html':
            writer = HTMLWriter(self, outdir)
        elif format is 'tmprefs':
            writer = TextMateWriter(self, outdir)
        else:
            raise ValueError("E: format must be one of %r but is %r" % (self.VALID_FORMATS, format))
        if not epaths:
            epaths = self.get_epaths()
        return writer.write(epaths)

    @deprecated(info="Use write() or one of the Writer classes instead.")
    def write2(self, outdir, dataformat, epaths=None, timestamp=True, data_callback=None): # IGNORE:W0621
        '''
        Write current data to a file at path adapted from 
        C{outdir/<date>/<timestamp>/<primary>-<secondary>.<dataformat>}.
               
        @param outdir: base path on which to build 
        @type outdir: C{string}
        @param dataformat: write data in this format, e.g. 'csv' or 'html'
        @type dataformat: C{string}
        @param epaths: list of epaths to write data for.
        @type epaths: C{list<string>}
        @param timestamp: if False, the path mask above becomes
            C{outdir/<date>/<primary>-<secondar>.<syntax>}.
            Warning: existing files may be overwritten when False.
        @type timestamp: C{bool}
        @param data_callback: a callback function that gets passed
            the complete data so that it may transform it.
        @type data_callback: C{function}
        '''
        if not self.initialized:
            raise InvalidStateError("Database must be initialize'd before calling write()")
        method = "to" + dataformat
        if not hasattr(self, method):
            raise ValueError("E: method to%s() not found. Is the value '%s' for param 'dataformat' correct?" % (dataformat, dataformat))
        stamp = str(tstamp())
        if timestamp:
            outdir = os.path.join(outdir, stamp)
        try:
            if not os.path.exists(outdir):
                os.makedirs(outdir, 0o755)
        except Exception as e:
            raise IOError("E: couldn't create outdir. The error message was: %s" % e)
        if not epaths:
            epaths = self.get_epaths()
        for epath in epaths:
            curdata = (getattr(self, method))(epath)
            if curdata is None or len(str(curdata)) == 0:
                continue
            comps = epath.split("/")
            if len(comps) == 1:
                fullpath = os.path.join(outdir, comps[0])
            else:
                fullpath = os.path.join(outdir, comps[0] + "-" + comps[1])
            fullpath += "." + dataformat
            if data_callback:
                try:
                    curdata = data_callback(curdata)
                except Exception as e:  # IGNORE:W0703
                    if DEBUG:
                        print(e)
                    else:
                        raise(e)
            try:
                write_encoded(fullpath, curdata, 'ascii', 'xmlcharrefreplace')
            except Exception as e:
                raise(e)
    
    @deprecated(info="Use HTMLWriter instead.")
    def tohtml(self, epath, convert_links=False, value_callback=None):
        def __construct_table(title, cols, rows):
            thead = ''
            tbody = ''
            table = '''
        <table summary="sphinx homepage data">
            <thead>
                %s
            </thead>
            <tbody>
                %s
            </tbody>
        </table>'''
            thead += '<tr>'
            for col in cols:
                thead += "<td>%s</td>" % col
            thead += '</tr>' 
            i = 0
            indent = ' ' * 16
            for item in rows:
                if i == 0:
                    tbody += "<tr>"
                else:
                    tbody += "%s<tr>" % indent
                for col in cols:
                    itm = item[col]
                    if convert_links:
                        itm = re.sub(urlpat, "<a href=\\1>\\1</a>", itm)
                    if value_callback:
                        itm = value_callback(itm)
                    #itm = Entity.encode(itm, skip=['\n', '\r'])
                    itm = html_escape(itm)
                    itm = re.sub('(\r\n|\n)', '<br>', itm)
                    tbody += "<td>%s</td>" % itm
                tbody += "</tr>%s" % os.linesep
                i += 1
            table = table % (thead, tbody[:-1])
            result = '<div class="title"><p>%s</p></div>' % title
            result += table
            return result
        if not self.initialized:
            raise InvalidStateError("Database must be initialize'd before calling tohtml()")
        urlpat = re.compile(constants.HTTP_URL_REGEX, re.VERBOSE | re.IGNORECASE) #@UnusedVariable
        html_template = ''
        thisdir = os.path.abspath(os.path.dirname(__file__))
        htmlfilesdir = 'htmlfiles'
        try:
            f = codecs.open(os.path.join(thisdir, htmlfilesdir, 'template.html'), 'r')
            try:
                for line in f:
                    html_template += line
            finally:
                f.close()
        except Exception as e:
            raise ValueError("E: couldn't read HTML template file. The error message was: %s" % e)
        styles = '<style type="text/css">' + os.linesep
        indent = ' ' * 12
        try:
            f = codecs.open(os.path.join(thisdir, htmlfilesdir, 'template.css'), 'r')
            try:
                for line in f:
                    styles += '%s%s' % (indent, line)
            finally:
                f.close()
        except Exception as e:
            raise ValueError("E: couldn't read CSS template file. The error message was: %s" % e)
        indent = ' ' * 8
        styles += '%s</style>' % indent
        rows = self.get_data(epath)
        cols = list(rows[0].keys())
        comps = epath.split('/')[1:]
        title = "%s" % string.capwords(' '.join(comps))
        body = __construct_table(title, cols, rows)
        html = html_template.replace("%BODY%", body)
        html = html.replace("%STYLES%", styles)
        return html
            
    @deprecated(info="Use CSVWriter instead.")
    def tocsv(self, epath, colsep=",", rowsep=os.linesep, value_callback=None):
        r'''
        Given an element path (epath for short) convert the data found
        at an attribute that has a name equal to this epath to CSV format.
        
        Example for a value callback function, which replaces an English
        based decimal point with a German one:
        
            >>> def replace_decimal_point(value):
            ...     return re.sub(r'(\d+)\.(\d+)', "\\1,\\2", value)
                
        @param epath: element path as C{<primary>/<secondary>}, 
            e.g. C{type/directives}
        @type epath: C{string}
        @param colsep: a string to use as column delimiter. defaults to comma,
            but can also be semicolon in some locales. 
            see: http://en.wikipedia.org/wiki/Comma-separated_values
        @type colsep: C{string}
        @param rowsep: a string to use as row delimiter.
        @type rowsep: C{string}
        @param value_callback: a callback function that gets passed the 
            current row's value one cell at a time. Must return a string
            representing the tranformed value.
        @type value_callback: C{function}
        '''
        if not self.initialized:
            raise InvalidStateError("Database must be initialize'd before calling tocsv()")
        items = self[epath]
        result = ""
        if len(items) == 0:
            return result
        else:
            # get column names from the first dict in the items list
            # this assumes that each item's dict has the same layout
            # which should always be true considering how this database
            # is constructed
            rows = []
            columns = list(items[0].keys())
            curdata = colsep.join(columns)
            rows.append(curdata)
            for item in items:
                curdata = ''
                for column in columns:
                    value = item[column]
                    # sanitize
                    if value_callback:
                        value = value_callback(value)
                    value = value.replace('"', '""')
                    # value = value.replace('\n', r'\n')
                    # value = value.replace('\r', r'\r')
                    # value = value.replace('\t', r'\t')
                    value = '"' + value + '"'
                    curdata += value + colsep
                curdata = curdata[:-1] # remove trailing colsep
                rows.append(curdata)
            result = rowsep.join(rows)
            return result                    


if __name__ == '__main__':
    
    # some value callbacks for CSVWriter
    def to_german_decimals(data, row, header):  # IGNORE:W0613
        return re.sub(r'(\d+)\.(\d+)', "\\1,\\2", data)
    def to_german_csv(data, row, header):  # IGNORE:W0613
        data = data.replace(",", ";")
        return re.sub(r'(\d+)\.(\d+)', "\\1,\\2", data)
    def linkify_tabledata(data, row, header):  # IGNORE:W0613
        return re.sub(r'<td>(http://.*?)</td>', '<td><a href="\\1">\\1</a></td>', data)
    
    print(sys.version)
    
    tests_site_url = "file://" + os.path.join(os.path.abspath('.'), "tests", "sphinx_pocoo_org")
    db = SphinxDatabase(tests_site_url)
    db.initialize()
    data = db.get_data('metadata*')

    print(("len(db) = %d" % len(db)))
    if data:
        print(("len(data) = %d" % len(data)))
    
    outdir = 'tests/sphinxhp-data'
    cw = CSVWriter(db, os.path.join(outdir, 'csv'))
    cw.colsep = ';'  # German CSV format
    cw.value_callback = to_german_decimals
    print(cw.write())
    
    tmw = TextMateWriter(db, os.path.join(outdir, 'tmprefs'))
    print(tmw.write())
    
    hw = HTMLWriter(db, os.path.join(outdir, 'html'))
    print(hw.write())

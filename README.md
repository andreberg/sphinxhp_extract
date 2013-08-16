# Introduction

Sphinx Homepage Data Extractor is a Python script which extracts  
relevant syntax data such as names for directives and roles and  
then converts this data to a number of output formats such as   
CSV, HTML (in a report similar to Ned Batchelder's coverage.py),  
TextMate prefs and finally text files with Ruby/Python lists.

It was made primarily for my [SphinxDoc.tmbundle](http://github.com/andreberg/SphinxDoc.tmbundle.git) to update the  
auto-completion lists.

# Usage

`cd` into this source directory in a terminal and just run `main.py`,  
for example:

`python main.py -h` 

or 

`python main.py --outdir OUTDIR --force --formats all --verbose`

# Copyright

Created by André Berg on 2011-09-29.  
Copyright Berg Media 2011, 2013. All rights reserved.

# License

Licensed under the Apache License, Version 2.0 (the "License");  
you may not use this file except in compliance with the License.  
You may obtain a copy of the License at

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software  
distributed under the License is distributed on an "AS IS" BASIS,  
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
See the License for the specific language governing permissions and  
limitations under the License.

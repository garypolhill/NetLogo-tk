#!/usr/bin/python3
"""scripts.py
This module is designed to work with nlogo.py and provides classes that
implement script templates.
"""

# Copyright (C) 2018  The James Hutton Institute
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public Licence as published by
# the Free Software Foundation, either version 3 of the Licence, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public Licence for more details.
#
# You should have received a copy of the GNU General Public Licence
# along with this program.  If not, see <https://www.gnu.org/licences/>.
__version__ = "0.1"
__author__ = "Gary Polhill"

################################################################################
# ProgressScript Class
################################################################################

class ProgressScript:

    def __init__(self, file_name = "progress.sh"):
        self.file_name = file_name

    def writeScript(self):
        try:
            fp = io.open(self.file_name, "w")
        except IOError as e:
            sys.stderr.write("Error creating file %s: %s\n"%(file_name, e.strerror))
        fp.write(u'''#!/bin/sh
if [[ "`uname -s`" == "Darwin" ]]
then
    date -j -f "%I:%M:%S %p %e-%b-%Y" "10:51:38 AM 12-Apr-2022" +"%s"
elif [[ "`uname -s`" == "Linux" ]]
then
    date -d "10:51:38.930 PM 12-Apr-2022" +"%s"
else
    echo "Unknown operating system \"`uname -s`\""
    exit 1
fi
        '''.format(nrun = self.nruns, svr_cores = self.cores,
                    name = self.name, time = self.time))

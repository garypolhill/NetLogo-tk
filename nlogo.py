#!/usr/bin/python3
"""nlogo.py
This module contains classes for reading and working with a NetLogo model.
Run from the command line, it can be used to:

* Extract all the parameters from the model's GUI tab into a CSV file
  (This can then be used in a subsequent call to create an experiment)

  ./nlogo.py <nlogo file> param <file to save parameters to>

* Print a list of the experiments from the model's behaviour space

  ./nlogo.py <nlogo file> expt

* Split an experiment's settings into individual experiments

  ./nlogo.py <nlogo file> split <experiment name> <experiment XML file>

* Prepare a script to run all the split experiments with Sun Grid Engine

  ./nlogo.py <nlogo file> splitq <experiment name> <experiment XML file>
                                 <file to save SGE submission script to>

* Prepare a Monte Carlo sample of parameter space

  ./nlogo.py <nlogo file> monte <parameter file> <tick number to stop at>
                                <number of samples> <experiment XML file>

  Note: if the number of samples is large, the XML library used by NetLogo
  to read in the experiment file can cause out-of-memory and garbage
  collection errors, or result in the model taking a long time to run. Use
  number of samples > 10000 with caution.

  The created experiment file automatically collects data from plot pens
  and monitors each step.

* Prepare a Monte Carlo sample of parameter space with a shell script to
  run all the options with Sun Grid Engine

  ./nlogo.py <nlogo file> montq <parameter file> <tick number to stop at>
                                <number of samples> <experiment XML file>
                                <file to save SGE submission script to>

  You can then submit the jobs with qsub <SGE submission script>

A typical workflow would be to run this with param and then montq, before
qsubbing the submission script. Once you've extracted the results you want
from the outputs, you could then use, for example bruteABC.py to analyse
the results.

Other potentially useful tools (for future implementation)

* Extract and collate outputs from NetLogo experiments in an XML file

* Automatically split up large sample sizes for monte and montq into
  chunks of, say, 20000 runs at a time. (DONE)

* Creata a qsub script to run a BehaviorSpace experiment in parallel (DONE)

* Parse code and do things with it, like extracting an ontology, or UML
  diagrams

* Automatically add a licence (e.g. GNU GPL) section to the Info tab

* Check progress with experiment runs by looking for output files
"""
# Copyright (C) 2018  The James Hutton Institute & University of Edinburgh
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
__version__ = "0.5"
__author__ = "Gary Polhill"

# Imports
import io
import os
import re
import sys
import math
import shutil
import random as rnd
import xml.etree.ElementTree as xml

def lineBreak(str, indent = "", tabstop = 8):
    (width, height) = shutil.get_terminal_size(fallback = (80, 24))

    indent = indent.replace("\t", " " * tabstop)
    ret = []
    line = 0
    while len(str) > 0:
        line += 1
        ind = "" if line == 1 else indent
        width_left = len(str) + len(ind)
        if width_left <= width:
            ret.append(ind + str)
            str = ""
        else:
            lwd = width + len(ind)
            lstr = str[:lwd]
            str = str[lwd:]
            space = lstr.rfind(" ")
            if space < 0:
                ret.append(ind + lstr)
            else:
                ret.append(ind + lstr[:space])
                str = lstr[(space + 1):] + str
    return ret

def parseBoolean(s):
    if s == "True":
        return True
    elif s == "False":
        return False
    else:
        sys.stderr.print("BUG! String \"{s}\" is not \"True\" or \"False\"".format(s = s))
        sys.exit(1)

################################################################################
# NLogoError Class
#
#   #   #  #       ###    ####   ###   #####  ####   ####    ###   ####
#   ##  #  #      #   #  #      #   #  #      #   #  #   #  #   #  #   #
#   # # #  #      #   #  # ###  #   #  ####   ####   ####   #   #  ####
#   #  ##  #      #   #  #   #  #   #  #      #   #  #   #  #   #  #   #
#   #   #  #####   ###    ###    ###   #####  #   #  #   #   ###   #   #
#
################################################################################

class NLogoError(Exception):
    """
    Bespoke error handler class, allowing tracking of cause, recovery options
    for the user, and an indication of whether this is a bug. Using these
    exceptions allows clean recovery when in GUI mode.
    """
    def __init__(self, message, cause = None, recovery = None, bug = False):
        Exception.__init__(message)
        self.message = message
        self.cause = cause
        self.recoverable = False
        self.recoveryMessage = "Cannot recover from this error"
        if not recovery is None:
            self.recoverable = True
            self.recoveryMessage = recovery
        self.bug = bug


################################################################################
# Widget Class
#
#   #   #  ###  ####    ####  #####  #####
#   #   #   #   #   #  #      #        #
#   # # #   #   #   #  # ###  ####     #
#   ## ##   #   #   #  #   #  #        #
#   #   #  ###  ####    ####  #####    #
#
################################################################################

class Widget:
    """
    The Widget class is a top-level class for all of the items that you can
    put on the GUI tab of a NetLogo model.
    """
    type = "<<UNDEF>>"
    def __init__(self, type, left, top, right, bottom, display, parameter,
                 output, info):
        self.type = type
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.display = display
        self.isParameter = parameter
        self.isOutput = output
        self.isInfo = info

    @staticmethod
    def read(fp):
        """
        Reads the widgets section from a NetLogo file, returning an array
        of widgets read
        """
        typestr = fp.readline()
        widgets = []
        while(typestr[0:-1] != "@#$#@#$#@"):
            typestr = typestr.strip()

            if typestr == GraphicsWindow.type:
                widgets.append(GraphicsWindow.read(fp))
            elif typestr == Button.type:
                widgets.append(Button.read(fp))
            elif typestr == Plot.type:
                widgets.append(Plot.read(fp))
            elif typestr == TextBox.type:
                widgets.append(TextBox.read(fp))
            elif typestr == Switch.type:
                widgets.append(Switch.read(fp))
            elif typestr == Chooser.type:
                widgets.append(Chooser.read(fp))
            elif typestr == Slider.type:
                widgets.append(Slider.read(fp))
            elif typestr == Monitor.type:
                widgets.append(Monitor.read(fp))
            elif typestr == OutputArea.type:
                widgets.append(OutputArea.read(fp))
            elif typestr == InputBox.type:
                widgets.append(InputBox.read(fp))
            else:
                sys.stderr.write("Unrecognized widget type: %s\n"%(typestr))
                while(typestr.strip() != ""):
                    typestr = fp.readline()

            typestr = fp.readline()
            if typestr == "":
                break
            if typestr.strip() == '':
                typestr = fp.readline()

        return widgets

################################################################################
# GraphicsWindow Class
################################################################################

class GraphicsWindow(Widget):
    """
    The GraphicsWindow class is a subclass of Widget that contains the space
    """
    type = "GRAPHICS-WINDOW"
    def __init__(self, left, top, right, bottom, patch_size, font_size, x_wrap,
                 y_wrap, min_pxcor, max_pxcor, min_pycor, max_pycor, update_mode,
                 show_ticks, tick_label, frame_rate):
        Widget.__init__(self, GraphicsWindow.type, left, top, right, bottom, "",
                        False, True, False)
        self.patchSize = patch_size
        self.fontSize = font_size
        self.xWrap = x_wrap
        self.yWrap = y_wrap
        self.minPXCor = min_pxcor
        self.maxPXCor = max_pxcor
        self.minPYCor = min_pycor
        self.maxPYCor = max_pycor
        self.updateMode = update_mode
        self.showTicks = show_ticks
        self.tickLabel = tick_label
        self.frameRate = frame_rate

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        res1 = fp.readline()
        res2 = fp.readline()
        patch_size = float(fp.readline())
        res3 = fp.readline()
        font_size = int(fp.readline())
        res4 = fp.readline()
        res5 = fp.readline()
        res6 = fp.readline()
        res7 = fp.readline()
        x_wrap = fp.readline().strip() == "1"
        y_wrap = fp.readline().strip() == "1"
        res8 = fp.readline()
        min_pxcor = int(fp.readline())
        max_pxcor = int(fp.readline())
        min_pycor = int(fp.readline())
        max_pycor = int(fp.readline())
        update_mode = int(fp.readline())
        res9 = fp.readline()
        show_ticks = fp.readline().strip() == "1"
        tick_label = fp.readline().strip()
        frame_rate = float(fp.readline())

        return GraphicsWindow(left, top, right, bottom, patch_size, font_size,
                              x_wrap, y_wrap, min_pxcor, max_pxcor, min_pycor,
                              max_pycor, update_mode, show_ticks, tick_label,
                              frame_rate)

################################################################################
# Button Class
################################################################################

class Button(Widget):
    """
    The Button class is a subclass of Widget containing a button
    """
    type = "BUTTON"
    def __init__(self, left, top, right, bottom, display, code, forever,
                 button_type, action_key, always_enable):
        Widget.__init__(self, Button.type, left, top, right, bottom, display,
                        False, False, False)
        self.code = code
        self.forever = forever
        self.buttonType = button_type
        self.actionKey = action_key
        self.alwaysEnable = always_enable

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        code = fp.readline().strip()
        forever = (fp.readline().strip() == "T")
        res1 = fp.readline()
        res2 = fp.readline()
        button_type = fp.readline().strip()
        res3 = fp.readline()
        action_key = fp.readline().strip()
        res4 = fp.readline()
        res5 = fp.readline()
        always_enable = (int(fp.readline()) == 1)

        return Button(left, top, right, bottom, display, code, forever,
                      button_type, action_key, always_enable)

################################################################################
# Parameter Class
#
#   ####     #    ####     #    #   #  #####  #####  #####  ####
#   #   #   # #   #   #   # #   ## ##  #        #    #      #   #
#   ####   #   #  ####   #   #  # # #  ####     #    ####   ####
#   #      #####  #   #  #####  #   #  #        #    #      #   #
#   #      #   #  #   #  #   #  #   #  #####    #    #####  #   #
#
################################################################################

class Parameter(Widget):
    """
    The Parameter class is an abstract subclass of Widget for all parameter widgets.
    Subclasses include Slider, Switch, Chooser and InputBox
    """
    def __init__(self, type, left, top, right, bottom, display):
        Widget.__init__(self, type, left, top, right, bottom, display, True, False, False)
        self.varname = '<<UNDEF>>'
        self.default = 'NA'
        self.value = 'NA'
        self.datatype = 'string'
        self.constrained = False
        self.rangeConstraint = False
        self.setConstraint = False
        self.otherParamConstraint = False

    def variable(self):
        return self.varname

    def settingStr(self):
        return str(self.value)

    def datatypeStr(self):
        return str(self.datatype)

    def setValue(self, value):
        self.value = value

################################################################################
# Output Class
################################################################################

class Output(Widget):
    """
    The Output class is an abstract subclass of Widget containing some output.
    Subclasses include Plot, Monitor and OutputArea
    """
    def __init__(self, type, left, top, right, bottom, display):
        Widget.__init__(self, type, left, top, right, bottom, display, False, True, False)

################################################################################
# Info Class
################################################################################

class Info(Widget):
    """
    The Info class is an abstract subclass of Widget containing information.
    TextBox is the subclass of Info.
    """
    def __init__(self, type, left, top, right, bottom, display):
        Widget.__init__(self, type, left, top, right, bottom, display, False, False, True)

################################################################################
# Plot Class
################################################################################

class Plot(Output):
    """
    Plot widget
    """
    type = "PLOT"
    def __init__(self, left, top, right, bottom, display, xaxis, yaxis, xmin,
                 xmax, ymin, ymax, autoplot_on, legend_on, code1, code2):
        Output.__init__(self, Plot.type, left, top, right, bottom, display)
        self.xaxis = xaxis
        self.yaxis = yaxis
        self.xmin = xmin
        self.ymin = ymin
        self.ymax = ymax
        self.autoplotOn = autoplot_on
        self.legendOn = legend_on
        self.code1 = code1
        self.code2 = code2
        self.pens = {}

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        xaxis = fp.readline().strip()
        yaxis = fp.readline().strip()
        xmin = float(fp.readline())
        xmax = float(fp.readline())
        ymin = float(fp.readline())
        ymax = float(fp.readline())
        autoplot_on = (fp.readline().strip() == "true")
        legend_on = (fp.readline().strip() == "true")
        codes = (fp.readline().strip().split('" "'))

        plot = Plot(left, right, top, bottom, display, xaxis, yaxis,
                    xmin, xmax, ymin, ymax, autoplot_on, legend_on,
                    codes[0][1:-1], codes[1][0:-2])
        if fp.readline().strip() == "PENS":
            penstr = fp.readline().strip()
            while penstr != '':
                plot.addPen(Pen.parse(penstr, display))
                penstr = fp.readline().strip()

        return plot

    def addPen(self, pen):
        self.pens[pen.display] = pen

    def getPens(self):
        return self.pens.values()

    def getPenDict(self):
        return self.pens

################################################################################
# Pen Class
################################################################################

class Pen:
    """
    The Pen class contains data for each pen of a Plot
    """
    def __init__(self, display, interval, mode, colour, in_legend, setup_code,
                 update_code, plot_name):
        self.display = display
        self.interval = interval
        self.mode = mode
        self.colour = colour
        self.inLegend = in_legend
        self.setupCode = setup_code
        self.updateCode = update_code
        self.plotName = plot_name

    @staticmethod
    def parse(penstr, plot_name):
        words = penstr.split()
        display = words[0]
        i = 1
        while not display.endswith('"'):
            display = display + " " + words[i]
            i = i + 1
        interval = float(words[i])
        mode = int(words[i + 1])
        colour = int(words[i + 2])
        in_legend = (words[i + 3] == "true")
        setup_code = words[i + 4]
        i = i + 5
        while setup_code.endswith('\\"') or not setup_code.endswith('"'):
            setup_code = setup_code + " " + words[i]
            i = i + 1
        update_code = " ".join(words[i:])
        return Pen(display, interval, mode, colour, in_legend, setup_code, update_code, plot_name)

################################################################################
# TextBox Class
################################################################################

class TextBox(Info):
    """
    TextBox is an Info containing some text
    """
    type = "TEXTBOX"
    def __init__(self, left, top, right, bottom, display, font_size, colour,
                 transparent):
        Info.__init__(self, TextBox.type, left, top, right, bottom, display)
        self.fontSize = font_size
        self.colour = colour
        self.transparent = transparent

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        font_size = int(fp.readline())
        colour = float(fp.readline())
        txt = fp.readline().strip()
        transparent = (txt == 'true' or txt == '1' or txt == 'T')
        return TextBox(left, top, right, bottom, display, font_size, colour,
                       transparent)

################################################################################
# Switch Class
################################################################################

class Switch(Parameter):
    """
    Switch Parameter widget
    """
    type = "SWITCH"
    def __init__(self, left, top, right, bottom, display, varname, on):
        Parameter.__init__(self, Switch.type, left, top, right, bottom, display)
        self.varname = varname
        self.isSwitchedOn = on
        self.value = self.isSwitchedOn
        self.datatype = 'boolean'
        self.constrained = True
        self.setConstraint = True

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        varname = fp.readline().strip()
        txt = fp.readline().strip()
        on = (txt == '0')
        res1 = fp.readline()
        res2 = fp.readline()
        return Switch(left, top, right, bottom, display, varname, on)

    def getConstraintSet(self):
        return [True, False]

################################################################################
# Chooser Class
################################################################################

class Chooser(Parameter):
    """
    Chooser Parameter widget
    """
    type = "CHOOSER"
    def __init__(self, left, top, right, bottom, display, varname, choices,
                 selection):
        Parameter.__init__(self, Chooser.type, left, top, right, bottom, display)
        self.varname = varname
        self.choices = choices
        self.selection = selection
        self.value = self.selection
        self.datatype = 'integer'
        self.constrained = True
        self.setConstraint = False

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        varname = fp.readline().strip()
        txt = fp.readline().strip()
        words = txt.split()
        choices = []
        choices.append(words[0])
        i = 1
        j = 0
        while i < len(words):
            while choices[j].startswith('"') and not choices[j].endswith('"'):
                choices[j] = choices[j] + " " + words[i]
                i = i + 1
            if i >= len(words):
                break
            choices.append(words[i])
            j = j + 1
            i = i + 1
        selection = int(fp.readline())
        return Chooser(left, top, right, bottom, display, varname, choices,
                       selection)

    def getSelectionStr(self):
        return self.choices[self.selection]

    def getConstraintSet(self):
        return self.choices

    def getOptionIndex(self, option):
        if option in self.choices:
            return self.choices.index(option)
        elif ('"' + option + '"') in self.choices:
            return self.choices.index('"' + minimum + '"')
        elif option == "NA":
            return "NA"
        else:
            opt = option
            if not isinstance(option, int):
                if not option.isdigit():
                    sys.stderr.write("Error: \"{value}\" is not an option for chooser {var} ({opts})\n".format(
                        value = option, var = self.varname,
                        opts = ", ".join([str(x) for x in self.choices])))
                opt = int(option)
                    
            if opt < 0 or opt >= len(self.choices):
                sys.stderr.write("Error: index {value} is not in the range of index values for chooser {var} ([0, {max}[)\n".format(
                    value = opt, var = self.varname, max = len(self.choices)
                ))
                sys.exit(1)
            return opt

    def getOptionValue(self, ix):
        if isinstance(ix, int) and ix >= 0 and ix < len(self.choices):
            return self.choices[ix]
        else:
            sys.stderr.write("BUG! getOptionValue() sent \"{value}\" -- should be integer in range [0, {max}[\n".format(value = ix, max = len(self.choices)))


################################################################################
# Slider Class
################################################################################

class Slider(Parameter):
    """
    Slider Parameter widget
    """
    type = "SLIDER"
    def __init__(self, left, top, right, bottom, display, varname, min, max,
                 default, step, units, orientation):
        Parameter.__init__(self, Slider.type, left, top, right, bottom, display)
        self.varname = varname
        self.minimum = min
        self.maximum = max
        self.default = default
        self.step = step
        self.units = units
        self.isHorizontal = (orientation == "HORIZONTAL")
        self.value = self.default
        self.datatype = 'numeric'
        self.constrained = True         # Strictly, you can set sliders outwith 
                                        # their range
        self.rangeConstraint = True
        self.minOther = False
        self.maxOther = False
        try:
            float(min)
        except ValueError:
            self.otherParamConstraint = True
            self.minOther = True
        try:
            float(max)
        except ValueError:
            self.otherParamConstraint = True
            self.maxOther = True


    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        varname = fp.readline().strip()
        min = fp.readline().strip()
        max = fp.readline().strip()
        default = float(fp.readline())
        step = fp.readline().strip()
        res1 = fp.readline()
        units = fp.readline().strip()
        orientation = fp.readline().strip()
        return Slider(left, top, right, bottom, display, varname, min, max,
                      default, step, units, orientation)

    def getMinimumConstraint(self):
        return self.minimum
    
    def getMaximumConstraint(self):
        return self.maximum

    def getNumericalMinConstraint(self, param_dict):
        if self.minOther:
            if self.minimum in param_dict:
                param = param_dict[self.minimum]
                if isinstance(param, Slider):
                    dict_cpy = param_dict.copy()
                    dict_cpy.pop(self.minimum)      # Stop infinite recursion
                    return param.getNumericalMinConstraint(dict_cpy)
                elif isinstance(param, Parameter) and param.datatype == "numeric":
                    return float(param.value)
                elif isinstance(param, float):
                    return param
                elif isinstance(param, int):
                    return float(param)
            return 'NA'
        else:
            return float(self.minimum)

    def getNumericalMaxConstraint(self, param_dict):
        if self.maxOther:
            if self.maximum in param_dict:
                param = param_dict[self.maximum]
                if isinstance(param, Slider):
                    dict_cpy = param_dict.copy()
                    dict_cpy.pop(self.maximum)      # Stop infinite recursion
                    return param.getNumericalMaxConstraint(dict_cpy)
                elif isinstance(param, Parameter) and param.datatype == "numeric":
                    return float(param.value)
                elif isinstance(param, float):
                    return param
                elif isinstance(param, int):
                    return float(param)
            return 'NA'
        else:
            return float(self.maximum)


################################################################################
# Monitor Class
################################################################################

class Monitor(Output):
    """
    Monitor Output Widget
    """
    type = "MONITOR"
    def __init__(self, left, top, right, bottom, display, source, precision,
                 font_size):
        Output.__init__(self, Monitor.type, left, top, right, bottom, display)
        self.source = source
        self.precision = precision
        self.fontSize = font_size

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        display = fp.readline().strip()
        source = fp.readline().strip().replace("\\\"", "\"")
        precision = int(fp.readline())
        res1 = fp.readline()
        font_size = int(fp.readline())
        return Monitor(left, top, right, bottom, display, source, precision,
                       font_size)

################################################################################
# OutputArea Class
################################################################################

class OutputArea(Output):
    """
    OutputArea Output widget
    """
    type = "OUTPUT"
    def __init__(self, left, top, right, bottom, font_size):
        Output.__init__(self, OutputArea.type, left, top, right, bottom, "")

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        font_size = int(fp.readline())
        display = ""
        return Output(left, top, right, bottom, font_size, display)

################################################################################
# InputBox Class
################################################################################

class InputBox(Parameter):
    """
    InputBox Parameter widget
    """
    type = "INPUTBOX"
    def __init__(self, left, top, right, bottom, varname, value, multiline,
                 datatype):
        Parameter.__init__(self, InputBox.type, left, top, right, bottom, "")
        self.varname = varname
        self.value = value
        self.isMultiline = multiline
        self.isNumeric = (datatype == "Number")
        self.isString = (datatype == "String")
        self.isCommand = (datatype == "String (command)")
        self.isReporter = (datatype == "String (reporter)")
        self.isColour = (datatype == "Color")
        if self.isNumeric or self.isColour:
            self.datatype = 'numeric'
        if self.isString:
            self.value = "\"" + value + "\""

    @staticmethod
    def read(fp):
        left = int(fp.readline())
        top = int(fp.readline())
        right = int(fp.readline())
        bottom = int(fp.readline())
        varname = fp.readline().strip()
        value = fp.readline().strip()
        txt = fp.readline().strip()
        multiline = (txt == 'true' or txt == '1' or txt == 'T')
        res1 = fp.readline()
        datatype = fp.readline().strip()
        return InputBox(left, top, right, bottom, varname, value, multiline,
                        datatype)

################################################################################
# BehaviorSpaceXMLError Class
################################################################################

class BahaviorSpaceXMLError(Exception):
    """
    Exception class for when there is unexpected content in the BehaviorSpace
    section of a NetLogo file.
    """
    def __init__(self, file, expected, found):
        self.file = file
        self.expected = expected
        self.found = found

    def __str__(self):
        return "BehaviorSpace XML format error in file %s: expected \"%s\", found \"%s\""%(self.file, self.expected, self.found)

################################################################################
# SteppedValue Class
################################################################################

class SteppedValue:
    """
    A class containing data from a stepped value parameter exploration in a
    BehaviorSpace
    """
    def __init__(self, variable, first, step, last):
        if step < 0.0 and first < last:
            raise ValueError("In BehaviorSpace, variable \"%s\" has negative step %f with start %f < stop %f"%(variable, step, first, last))
        elif step > 0.0 and first > last:
            raise ValueError("In BehaviorSpace, variable \"%s\" has step %f with start %f > stop %f"%(variable, step, first, last))
        elif step == 0.0 and first != last:
            raise ValueError("In BehaviorSpace, variable \"%s\" has step 0.0 with start %f != stop %f"%(variable, step, first, last))
        self.variable = variable
        self.first = first
        self.step = step
        self.last = last
        self.values = []
        self.values.append(first)
        while self.values[-1] < self.last:
            self.values.append(self.step + self.values[-1])

    def getValues(self):
        return self.values

    def getNValues(self):
        return len(self.values)

    @staticmethod
    def fromXML(xml, file_name):
        if xml.tag != "steppedValueSet":
            raise BehaviorSpaceXMLError(file_name, "steppedValueSet", xml.tag)
        return SteppedValue(xml.get("variable"), float(xml.get("first")),
                            float(xml.get("step")), float(xml.get("last")))

################################################################################
# EnumeratedValue Class
################################################################################

class EnumeratedValue:
    """
    A class containing data from an enumerated value parameter exploration
    in a BehaviorSpace
    """
    def __init__(self, variable, values):
        self.variable = variable
        if isinstance(values, list):
            self.values = values
        else:
            self.values = []
            self.values.append(values)

    def getValues(self):
        return self.values

    def getNValues(self):
        return len(self.values)

    @staticmethod
    def fromXML(xml, file_name):
        if xml.tag != "enumeratedValueSet":
            raise BehaviorSpaceXMLError(file_name, "enumeratedValueSet", xml.tag)

        variable = xml.get("variable")
        values = []
        for value in xml:
            if value.tag != "value":
                raise BehaviorSpaceXMLError(file_name, "value", value.tag)
            values.append(value.get("value"))

        return EnumeratedValue(variable, values)

################################################################################
# Experiment Class
#
#   #####  #   #  ####   #####  ####   ###  #   #  #####  #   #  #####
#   #       # #   #   #  #      #   #   #   ## ##  #      ##  #    #
#   ####     #    ####   ####   ####    #   # # #  ####   # # #    #
#   #       # #   #      #      #   #   #   #   #  #      #  ##    #
#   #####  #   #  #      #####  #   #  ###  #   #  #####  #   #    #
#
################################################################################

class Experiment:
    param_comment = "; nlogo.py added this code to save parameters and metrics"
    prog_comment = "; nlogo.py added this code to save progress"

    """
    Class containing data from a single BehaviorSpace experiment
    """
    def __init__(self, name, setup, go, final, time_limit, exit_condition,
                 metrics, stepped_values = [], enumerated_values = [],
                 repetitions = 1, sequential_run_order = True,
                 run_metrics_every_step = True, results = ".", metric_labels = []):
        self.name = name
        self.setup = setup
        self.go = go
        self.final = final
        self.timeLimit = time_limit
        self.exitCondition = exit_condition
        self.metrics = metrics
        if len(metric_labels) != len(metrics):
            self.metricLabels = [x for x in metrics]
        else:
            self.metricLabels = metric_labels
        self.steppedValueSet = stepped_values
        self.enumeratedValueSet = enumerated_values
        self.repetitions = int(repetitions)
        self.sequentialRunOrder = sequential_run_order
        self.runMetricsEveryStep = run_metrics_every_step
        self.results = results # Directory where any output should be
        self.addedProgress = (self.prog_comment in setup)
        self.addedFinalParametrics = (self.param_comment in final)

    def getMetrics(self):
        return self.metrics

    def getSteppedParameters(self):
        return self.steppedValueSet

    def getEnumeratedParameters(self):
        return self.enumeratedValueSet

    def getNRuns(self):
        runs = self.repetitions
        for param in self.steppedValueSet:
            runs *= param.getNValues()
        for param in self.enumeratedValueSet:
            runs *= param.getNValues()
        return runs

    def uniqueSettings(self, opts):
        """
        Return an array of all the runs in this experiment with unique
        parameter settings
        """
        experiments = []

        counters = {}
        maxes = {}
        for param in self.steppedValueSet:
            counters[param.variable] = 0
            maxes[param.variable] = param.getNValues()
        for param in self.enumeratedValueSet:
            if not opts.isParamSet(param.variable):
                counters[param.variable] = 0
                maxes[param.variable] = param.getNValues()

        done = False
        i = 1 
        n = self.getNRuns()
        if not opts.split_reps:
            n /= self.repetitions

        use_metrics = [m for m in self.metrics]
        if opts.rng_param != "" and not opts.rng_param in use_metrics:
            use_metrics.append(opts.rng_param)

        while not done:
            enumerated_values = []

            for param in self.steppedValueSet:
                # N.B. adding this single value to enumerated_values is
                # deliberate; the new experiment will have no stepped values
                enumerated_values.append(EnumeratedValue(param.variable,
                    param.getValues()[counters[param.variable]]))
            for param in self.enumeratedValueSet:
                if not opts.isParamSet(param.variable):
                    enumerated_values.append(EnumeratedValue(param.variable,
                        param.getValues()[counters[param.variable]]))

            # Make sure any RNG switch is set to the right value to cause new
            # seeds to be selected
            if opts.rng_switch != "":
                enumerated_values.append(EnumeratedValue(opts.rng_switch, "true"))
            elif opts.rng_no_switch != "":
                enumerated_values.append(EnumeratedValue(opts.rng_no_switch, "false"))


            reps = int(self.repetitions)
            if opts.split_reps:
                reps = 1
            for j in range(int(self.repetitions / reps)):
                new_name = "%s-%0*d" % (self.name, Batch.n_digits(n), i)

                # Set each directory parameter
                for param in opts.dir_params:
                    enumerated_values.append(EnumeratedValue(param,
                        Batch.outdir(opts, self.name, i, n)))
                for param in opts.file_params:
                    enumerated_values.append(EnumeratedValue(param,
                        opts.getUniqueFilename(param, self.name, i, n)))

                # Add the experiment
                experiments.append(Experiment(new_name, self.setup, self.go,
                    self.final, self.timeLimit, self.exitCondition, use_metrics,
                    [], enumerated_values, reps, self.sequentialRunOrder,
                    self.runMetricsEveryStep, Batch.outdir(opts, self.name, i, n)))
                i += 1

            for var in counters.keys():
                counters[var] += 1
                if counters[var] == maxes[var]:
                    counters[var] = 0
                else:
                    break

            done = all([v == 0 for v in counters.values()])

        return experiments

    @staticmethod
    def fromXMLString(str, file_name):
        """
        Parse a full <experiments>...</experiments> XML string into an
        array of Experiments, which is returned
        """
        experiments = []
        if str == None or str.strip() == "":
            return []
        xmlstr = xml.XML(str)
        if xmlstr.tag != "experiments":
            raise BehaviorSpaceXMLError(file_name, "experiments", xmlstr.tag)
        for exp in xmlstr:
            if exp.tag != "experiment":
                raise BehaviorSpaceXMLError(file_name, "experiment", exp.tag)
            repetitions = 1
            sequential_run_order = True
            run_metrics_every_step = True
            name = None
            for attr in exp.keys():
                if attr == "name":
                    name = exp.get(attr)
                elif attr == "repetitions":
                    repetitions = exp.get(attr)
                elif attr == "sequentialRunOrder":
                    sequential_run_order = (exp.get(attr) == "true")
                elif attr == "runMetricsEveryStep":
                    run_metrics_every_step = (exp.get(attr) == "true")
                else:
                    raise BehaviorSpaceXMLError(file_name,
                        "name|repetitions|sequentialRunOrder|runMetricsEveryStep",
                        attr)
            if name == None:
                raise BehaviorSpaceXMLError(file_name, "name",
                                            "no \"name\" attribute for experiment")
            setup = ""
            go = ""
            final = ""
            time_limit = None
            exit_condition = None
            metrics = []
            stepped_values = []
            enumerated_values = []

            for elem in exp:
                if elem.tag == "setup":
                    setup = elem.text
                elif elem.tag == "go":
                    go = elem.text
                elif elem.tag == "final":
                    final = elem.text
                elif elem.tag == "timeLimit":
                    time_limit = float(elem.get("steps"))
                    if time_limit == None:
                        raise BehaviorSpaceXML(file_name, "steps",
                                               "no \"steps\" attribute for timeLimit")
                elif elem.tag == "exitCondition":
                    exit_condition = elem.text
                elif elem.tag == "metric":
                    metrics.append(elem.text)
                elif elem.tag == "steppedValueSet":
                    stepped_values.append(SteppedValue.fromXML(elem, file_name))
                elif elem.tag == "enumeratedValueSet":
                    enumerated_values.append(EnumeratedValue.fromXML(elem, file_name))
                else:
                    raise BehaviorSpaceXML(file_name, "experiment sub-element", elem.tag)

            experiments.append(Experiment(name, setup, go, final, time_limit,
                               exit_condition, metrics, stepped_values,
                               enumerated_values, repetitions,
                               sequential_run_order, run_metrics_every_step))
        return experiments

    @staticmethod
    def fromWidgets(widgets, stop, opts):
        """
        Create an Experiment object from the parameter and output widgets on
        the GUI. Current parameter settings on the GUI will be used as the
        parameter values, and outputs used as metrics.
        """
        setup = opts.setup
        go = opts.go
        outputs = []
        params = []

        for w in widgets:
            if isinstance(w, Button):
                if(not opts.user_setup and (w.display == "setup" or w.code == "setup")):
                    setup = w.code.replace("\\n", "\n")
                elif(not opts.user_go and (w.display == "go" or w.code == "go")):
                    go = w.code.replace("\\n", "\n")
            elif isinstance(w, Output) and not isinstance(w, OutputArea):
                outputs.append(w)
            elif isinstance(w, Parameter):
                if opts.rng_param != "" and w.variable() == opts.rng_param:
                    outputs.append(w)   # Use the seed as a metric
                elif not w.variable() in opts.dir_params:
                    if opts.rng_switch != "" and w.variable() == opts.rng_switch:
                        w.setValue("true")
                    if opts.rng_no_switch != "" and w.variable() == opts.rng_no_switch:
                        w.setValue("false")
                    params.append(w)

        expt = None
        if isinstance(stop, int):
            expt = Experiment(opts.name, setup, go, "", stop, None, [])
        else:
            expt = Experiment(opts.name, setup, go, "", None, str(stop), [])
        expt = expt.withParameterSettings(params)
        for w in outputs:
            expt.addMetric(w)

        return expt

    def withParameterSettings(self, param):
        """
        Return a new Experiment the same as this one, but using the parameter
        settings contained in the param array
        """
        new_enum_set = []
        for p in param:
            if isinstance(p, Parameter):
                valuearr = []
                if p.datatypeStr() == 'string' and not p.settingStr().startswith('"') and not p.settingStr().startswith('&quot;'):
                    valuearr.append('"' + p.settingStr() + '"')
                else:
                    valuearr.append(p.settingStr())
                new_enum_set.append(EnumeratedValue(p.variable(), valuearr))
            else:
                new_enum_set.append(EnumeratedValue(p, param[p]))
        return Experiment(self.name, self.setup, self.go, self.final, self.timeLimit,
                          self.exitCondition, self.metrics, [], new_enum_set,
                          self.repetitions, self.sequentialRunOrder,
                          self.runMetricsEveryStep, metric_labels = self.metricLabels)

    def withSamples(self, samples):
        """
        Create an experiment from this one, changing the parameter settings to
        be set randomly from the array of samples passed as argument
        """
        param = {}
        for s in samples:
            s.newSample()
        for s in samples:
            name = s.param.variable()
            value = s.sample()
            param[name] = value
        return self.withParameterSettings(param)

    def withNSamples(self, samples, n, opts):
        """
        Create an array of experiments from this one, changing the parameter
        settings such that each is set randomly from the array of samples
        passed as argument
        """
        expts = []
        for i in range(0, n):
            new_name = "%s-%0*d" % (self.name, Batch.n_digits(n), i + 1)
            expt = self.withSamples(samples)
            expt.rename(new_name)
            if opts.save_csv:
                expt.finallySaveParamMetricsExpt()
            for param in opts.dir_params:
                expt.addEnumeratedValue(param, Batch.outdir(opts, self.name, i + 1, n))
            for param in opts.file_params:
                expt.addEnumeratedValue(param, opts.getUniqueFilename(param, self.name, i + 1, n))
            expt.results = Batch.outdir(opts, self.name, i + 1, n)
            expts.append(expt)
        return expts

    @staticmethod
    def writeExperimentHeader(fp):
        """
        Write the XML header to save the experiments as an XML file
        """
        fp.write(u"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        fp.write(u"<!DOCTYPE experiments SYSTEM \"behaviorspace.dtd\">\n")
        fp.write(u"<experiments>\n")

    @staticmethod
    def writeExperimentFooter(fp):
        """
        Write the XML footer to save the experiments as an XML file
        """
        fp.write(u"</experiments>\n")

    @staticmethod
    def writeExperiments(expts, opts):
        """
        Save an array of experiments to the XML file named on the command line
        """
        try:
            if not os.path.isdir(opts.xml_dir):
                os.mkdir(opts.xml_dir)
        except IOError as e:
            sys.stderr.write("Error checking/creating experiment directory \"{d}\": {s}\n".format(
                d = opts.xml_dir, s = e.strerror))
        written = Experiment.writeExperimentsToFile(opts.xml_dir + "/" + opts.arg_xml, expts, opts)
        if len(written) == 0:
            sys.exit(1)
        else:
            print("{n} experiments written to the following files:".format(n = len(expts)))
            for f in written:
                print("\t{file_name}".format(file_name = f))

    @staticmethod
    def writeExperimentsToFile(file_name, expts, opts):
        """
        Save an array of experiments as an XML file
        """
        written = []
        if opts.progress:
            for expt in expts:
                expt.addProgress(opts)

        if len(expts) <= opts.max_batch:
            try:
                fp = io.open(file_name, "w")
            except IOError as e:
                sys.stderr.write("Error creating file %s: %s\n"%(file_name, e.strerror))
                return written

            Experiment.writeExperimentHeader(fp)

            for expt in expts:
                expt.writeExperimentDetails(fp)

            Experiment.writeExperimentFooter(fp)
            fp.close()
            written.append(file_name)

        else:
            n_batch = math.ceil(len(expts) / opts.batch_size)
            for batch in range(0, n_batch):
                batch_str = "%0*d"%(Batch.n_digits(n_batch), batch + 1)
                batch_file = file_name[0:(len(file_name) - 4)] + "-" + batch_str + ".xml"

                try:
                    fp = io.open(batch_file, "w")
                except IOError as e:
                    sys.stderr.write("Error creating file %s: %s\n"%(batch_file, e.strerror))
                    return []

                Experiment.writeExperimentHeader(fp)

                batch_min = batch * opts.batch_size
                batch_max = batch_min + opts.batch_size
                if batch_max > len(expts):
                    batch_max = len(expts)

                for expt in expts[batch_min:batch_max]:
                    expt.writeExperimentDetails(fp)

                Experiment.writeExperimentFooter(fp)
                fp.close()
                written.append(batch_file)

        return written

    def writeExperimentDetails(self, fp):
        """
        Write the XML encoding of this Experiment to the file pointer fp
        """
        fp.write(u"  <experiment name=\"%s\" repetitions=\"%d\" sequentialRunOrder=\"%s\" runMetricsEveryStep=\"%s\">\n"
                 %(self.name, self.repetitions,
                   "true" if self.sequentialRunOrder else "false",
                   "true" if self.runMetricsEveryStep else "false"))
        if self.setup != "":
            fp.write(u"    <setup>%s</setup>\n" % self.escape(self.setup))
        if self.go != "":
            fp.write(u"    <go>%s</go>\n" % self.escape(self.go))
        if self.final != "":
            fp.write(u"    <final>\n%s\n    </final>\n" % self.escape(self.final))
        if self.timeLimit != None:
            fp.write(u"    <timeLimit steps=\"%d\"/>\n" % math.ceil(self.timeLimit))
        if self.exitCondition != None:
            fp.write(u"    <exitCondition>%s</exitCondition>\n" % self.escape(self.exitCondition))
        for m in self.metrics:
            fp.write(u"    <metric>%s</metric>\n" % self.escape(m))

        for v in self.steppedValueSet:
            fp.write(u"    <steppedValueSet variable=\"%s\" first=\"%f\" step=\"%f\" last=\"%f\"/>\n"
                     %(self.escape(v.variable), v.first, v.step, v.last))

        for v in self.enumeratedValueSet:
            fp.write(u"    <enumeratedValueSet variable=\"%s\">\n" % self.escape(v.variable))
            for w in v.values:
                fp.write(u"      <value value=\"%s\"/>\n" % self.escape(w))
            fp.write(u"    </enumeratedValueSet>\n")

        fp.write(u"  </experiment>\n")

    def escape(self, entry):
        """
        Escape ampersands, quotes and inequalities when writing XML data
        """
        string = str(entry)
        return string.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

    def writeExperiment(self, file_name):
        """
        Write this experiment to the named file
        """
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            sys.stderr.write("Error creating file %s: %s\n"%(file_name, e.strerror))
            return False

        Experiment.writeExperimentHeader(fp)

        self.writeExperimentDetails(fp)

        Experiment.writeExperimentFooter(fp)
        fp.close()

        return True

    def rename(self, new_name):
        self.name = str(new_name)

    def setReps(self, reps):
        self.repetitions = int(reps)

    def setSequentialRunOrder(self, seq):
        if isinstance(seq, str) and seq == "False":
            self.sequentialRunOrder = False 
        else:
            self.sequentialRunOrder = bool(seq)

    def setRunMetricsEveryStep(self, run):
        if osomstamce(run, str) and run == "False":
            self.runMetricsEveryStep = False
        else:
            self.runMetricsEveryStep = bool(run)

    def setSetup(self, setup):
        """
        Change the setup code of the experiment
        """
        if isinstance(setup, Button):
            self.setup = setup.code
        elif isinstance(setup, Experiment):
            self.setup = setup.setup
        else:
            self.setup = str(setup)

    def addProgress(self, opts):
        """
        Add code to the 'go' part of the experiment that writes the number of
        ticks to a file with a timestamp so that the progress can be inspected.
        Each line is formatted as:

        <ticks> / <time limit>: %H:%M:%S.%3N %p %d-%b-%y

        (N.B. %3N isn't available on all implementations of the date command)

        The implementation of the date-and-time command calls Java's
        java.text.SimpleDateFormat("hh:mm:ss.SSS a dd-MMM-yyyy")

        According to the Java documentation:

        hh (01-12) hour in am/pm
        mm (00-59) minute in hour
        ss (00-50) second in minute
        SSS (000-999) millisecond
        a (AM/PM) am/pm marker
        dd (01-31) day in month
        MMM short month name
        yyyy (0000-9999) year

        This command should have used ISO standard date format.
        """
        if not self.addedProgress:
            f = "behaviorspace-experiment-name \"-\" behaviorspace-run-number \"-prog.txt\""
            if self.results != "." and not opts.dup_setup:
                f = "\"{dir}/\" ".format(dir = self.results) + f
            f = "(word " + f + ")"
            self.setup += ("\n{c}\nfile-open {f}\n".format(c = self.prog_comment,
                f = f) + "file-print (word \"0 / {s}: \" date-and-time)\nfile-close".format(
                s = self.timeLimit))
            self.go += ("\nfile-open {f}\n".format(f = f) +
                "file-print (word ticks \" / {s}: \" date-and-time)\n".format(
                s = self.timeLimit) + "file-close")
            self.addedProgress = True

    def setGo(self, go):
        """
        Change the go command of the experiment
        """
        if isinstance(go, Button):
            self.go = go.code
        elif isinstance(go, Experiment):
            self.go = go.go
        else:
            self.go = str(go)

    def setFinal(self, final):
        """
        Change the final part of the experiment
        """
        if isinstance(final, Button):
            self.final = final.code
        elif isinstance(final, Experiment):
            self.final = final.final
        else:
            self.final = str(final)

    def finallySaveParamMetrics(self, file_name):
        """
        Put code in the final part of the experiment to save the parameters
        and metrics to a file. The code is added (once) rather than overwriting.
        """
        if not self.addedFinalParametrics:
            paramStr = ""
            wordStr = ""
            for v in self.steppedValueSet:
                paramStr = paramStr + v.variable + ","
                wordStr = wordStr + v.variable + " \",\" "
            for v in self.enumeratedValueSet:
                paramStr = paramStr + v.variable + ","
                wordStr = wordStr + v.variable + " \",\" "
            for i in range(len(self.metrics)):
                m = self.metrics[i]
                l = self.metricLabels[i]
                paramStr = paramStr + l.replace(",", ".").replace('"', ".") + ","
                wordStr = wordStr + "(" + m + ") \",\" "
            if self.results != ".":
                file_name = self.results + "/" + file_name
            self.final = '''
{comment}
ifelse file-exists? "{file}" [
    file-open "{file}"
] [
    file-open "{file}"
    file-print "{param}"
]
file-print (word {word})
file-close
; end of code to save parameters and metrics
            '''.format(comment = self.param_comment, file = file_name,
                param = paramStr[:-1], word = wordStr[:-5])
            self.addedFinalParametrics = True

    def finallySaveParamMetricsExpt(self):
        """
        Convenience method to add save of parameters and metrics using
        a default name
        """
        self.finallySaveParamMetrics(self.name + ".csv")

    def setTimeLimit(self, limit):
        """
        Set the time limit of the experiment
        """
        self.timeLimit = float(limit)

    def setExitCondition(self, exitCond):
        """
        Set the exit condition of the experiment
        """
        self.exitCondition = str(exitCond)

    def clearMetrics(self):
        """
        Clear the experiment's metrics
        """
        self.metrics = []

    def addMetric(self, metric):
        """
        Add metrics to the experiment
        """
        if isinstance(metric, Monitor):
            self.metrics.append(metric.source)
            self.metricLabels.append(metric.display)
        elif isinstance(metric, Plot):
            for p in metric.getPens():
                self.addMetric(p)
        elif isinstance(metric, Pen):
            code = metric.updateCode
            if code.startswith('"'):
                code = code[1:-1].replace('\\"', '"')
            if code.startswith('plot '):
                code = code[5:]
            if not code.startswith('histogram '):
                self.metrics.append(code)
                legend = metric.display
                if legend[0] == '\"':
                    legend = legend[1:]
                if legend[-1] == '\"':
                    legend = legend[:-1]
                legend = metric.plotName + "." + legend if legend != "default" else metric.plotName
                self.metricLabels.append(legend)
        elif isinstance(metric, Experiment):
            for i in range(len(metric.metrics)):
                self.addMetricLabelled(metric.metrics[i], metric.metricLabels[i])
        elif isinstance(metric, Parameter):
            self.metrics.append(metric.variable())
            self.metricLabels.append(metric.variable())
        elif not isinstance(metric, Output):
            self.metrics.append(str(metric))
            self.metricLabels.append(str(metric))

    def clearSteppedValueSet(self):
        """
        Clear the experiment's stepped value set
        """
        self.steppedValueSet = []

    def addSteppedValue(self, variable, first, step, last):
        """
        Add a new stepped value to the experiment
        """
        self.steppedValueSet.append(SteppedValue(str(variable), float(first), float(step), float(last)))

    def clearEnumeratedValueSet(self):
        """
        Clear the experiment's enumerated values
        """
        self.enumeratedValueSet = []

    def addEnumeratedValue(self, variable, values):
        """
        Add an enumerated value to the experiment
        """
        self.enumeratedValueSet.append(EnumeratedValue(str(variable), values))


################################################################################
# NetlogoModel Class
#
#   #   #  #####  #####  #       ###    ####   ###
#   ##  #  #        #    #      #   #  #      #   #
#   # # #  ####     #    #      #   #  # ###  #   #
#   #  ##  #        #    #      #   #  #   #  #   #
#   #   #  #####    #    #####   ###    ###    ###
#
################################################################################

class NetlogoModel:
    """
    The NetlogoModel class contains partially parsed elements of a Netlogo
    file, with a focus on extracting the widgets, parameters and experiments
    """
    def __init__(self, code, widgets, info, shapes, version, preview, sd,
                 behav, hubnet, link_shapes, settings, deltatick):
        self.code = code
        self.widgets = widgets
        self.info = info
        self.shapes = shapes
        self.version = version
        self.preview = preview
        self.sd = sd
        self.behav = behav
        self.hubnet = hubnet
        self.linkShapes = link_shapes
        self.settings = settings
        self.deltatick = deltatick
        self.params = {}
        self.expts = {}

    @staticmethod
    def readSection(fp):
        """
        Read a section of a Netlogo file
        """
        section = ""
        for line in fp:
            if line[0:-1] == "@#$#@#$#@":
                break
            section = section + line
        return section

    @staticmethod
    def read(opts):
        """
        Read in a Netlogo file. The opts object is expected to have a .model
        attribute containing the name of the file to open. The Options are
        passed in so that opts can check any parameters named in commandline
        options exist.
        """
        try:
            fp = io.open(opts.model_file)
        except IOError as e:
            sys.stderr.write("Error opening file %s: %s\n"%(opts.model_file, e.strerror))
            return False

        code = NetlogoModel.readSection(fp)

        widgets = Widget.read(fp)

        info = NetlogoModel.readSection(fp)

        shapes = NetlogoModel.readSection(fp)

        version = NetlogoModel.readSection(fp)
        version = version[0:-1]

        preview = NetlogoModel.readSection(fp)

        sd = NetlogoModel.readSection(fp)

        behav = Experiment.fromXMLString(NetlogoModel.readSection(fp), opts.model_file)

        hubnet = NetlogoModel.readSection(fp)

        link_shapes = NetlogoModel.readSection(fp)

        settings = NetlogoModel.readSection(fp)

        deltatick = NetlogoModel.readSection(fp)

        opts.setNetLogoModel(NetlogoModel(code, widgets, info, shapes, version,
            preview, sd, behav, hubnet, link_shapes, settings, deltatick))
        return opts.getNetLogoModel()

    def getParameters(self):
        """
        Return the parameters of the model as a dictionary keyed by parameter
        name and value the setting on the GUI
        """
        if len(self.params) == 0:
            for w in self.widgets:
                if(isinstance(w, Parameter)):
                    self.params[w.variable()] = w
        return self.params

    def getParameterNames(self):
        """
        Return a list of the names of the parameters
        """
        parnames = []
        for p in self.getParameters().keys():
            parnames.append(p)
        return parnames

    def getSetting(self, parname):
        """
        Return the setting of a parameter
        """
        pars = self.getParameters()
        if parname in pars:
            return pars[parname].settingStr()
        else:
            sys.stderr.write("Asked for setting of non-existent parameter \"{p}\"\n".format(parname))
            sys.exit(1)

    def getMonitors(self):
        monitors = {}
        for w in self.widgets:
            if(isinstance(w, Monitor)):
                monitors[w.display] = w
        return monitors

    def getPlots(self):
        plots = {}
        for w in self.widgets:
            if(isinstance(w, Plot)):
                plots[w.display] = w
        return plots

    def getExperiments(self):
        """
        Return the BehaviorSpace experiments as a dictionary keyed by name
        with values the Experiment object
        """
        if len(self.expts) == 0 and len(self.behav) != 0:
            for b in self.behav:
                self.expts[b.name] = b
        return self.expts

    def writeParameters(self, file_name):
        """
        Save the parameters to a file
        """
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            sys.stderr.write("Error creating file %s: %s\n"%(file_name, e.strerror))

        fp.write(u"parameter,type,setting,minimum,maximum\n")

        param = self.getParameters()

        for key in sorted(param.keys()):
            fp.write(u"%s,%s,%s"%(key, param[key].datatypeStr(), param[key].settingStr()))
            if param[key].datatypeStr() == 'numeric' or param[key].datatypeStr() == 'integer':
                if isinstance(param[key], Slider):
                    fp.write(u",%s,%s\n"%(str(param[key].minimum), str(param[key].maximum)))
                elif isinstance(param[key], Chooser):
                    fp.write(u",0,%d\n"%(len(param[key].choices) - 1))
                    # TO-DO use one-of instead of 0 and write options separated by |
                else:
                    fp.write(u",%s,%s\n"%(param[key].settingStr(), param[key].settingStr()))
            elif param[key].datatypeStr() == 'boolean':
                fp.write(u",true,false\n")
                # TO-DO have this as ,one-of,true|falae
            else:
                fp.write(u",NA,NA\n")

        fp.close()

    def printExperiments(self):
        """
        Print a list of experiments with their metrics and varied parameters
        """
        if len(self.behav) == 0:
            print("There are no experiments")
        else:
            print("Experiments:")
            for expt in self.behav:
                n = expt.getNRuns()

                print("\t" + expt.name + " (" + str(expt.getNRuns()) + (" run)" if n == 1 else " runs)") )

                m = 1
                for param in expt.steppedValueSet:
                    if param.getNValues() > 1:
                        print("\t\tparameter \"{pnm}\": {pn} steps".format(
                            pnm = param.variable, pn = param.getNValues()))
                for param in expt.enumeratedValueSet:
                    if param.getNValues() > 1:
                        print("\t\tparameter \"{pnm}\": {pn} samples".format(
                            pnm = param.variable, pn = param.getNValues()))
                for metric in expt.metrics:
                    print("\t\tmetric {mid}: \"{mstr}\"".format(mid = m, mstr = metric))
                    m += 1

    def splitExperiment(self, name, opts):
        """
        Split an experiment, saving the runs to the XML file, and returning the
        number of experiments created.
        """
        self.getExperiments()
        if len(self.behav) == 0:
            print("There are no experiments")
            return []
        elif name not in self.expts:
            print("There is no experiment named " + name)
            return []
        else:
            expt = self.expts[name]
            splitted = expt.uniqueSettings(opts)
            Experiment.writeExperiments(splitted, opts)
            return splitted

    def getVersion(self):
        return self.version

################################################################################
# Sample Class
#
#    ####    #    #   #  ####   #      #####
#   #       # #   ## ##  #   #  #      #
#    ###   #   #  # # #  ####   #      ####
#       #  #####  #   #  #      #      #
#   ####   #   #  #   #  #      #####  #####
#
################################################################################

class Sample:
    """
    The Sample class stores samples read in from a file created when saving
    parameters from a model. The CSV file can be edited by hand to indicate
    the parameters that are to be set in a Monte Carlo experiment.
    """

    def __init__(self, param, datatype, setting, minimum, maximum, params):
        self.param = param
        self.datatype = datatype
        self.options = []
        self.one_of = False
        self.min_is_param = False
        self.max_is_param = False
        self.sampled = False
        self.last_sample = None
        self.tagged = False

        if minimum == "one-of":
            choices = maximum.split("|")
            for choice in choices:
                if isinstance(self.param, Chooser):
                    self.options.append(self.param.getOptionValue(self.param.getOptionIndex(choice)))
                else:
                    self.options.append(choice)
            self.minimum = 0
            self.maximum = len(self.options)
            self.setting = "NA"
            self.one_of = True

        elif isinstance(self.param, Chooser):
            self.minimum = self.param.getOptionIndex(minimum)
            self.maximum = self.param.getOptionIndex(maximum)
            self.setting = self.param.getOptionIndex(setting)
        else:
            self.setting = setting
            self.minimum = minimum
            if minimum in params:
                self.minimum = params[minimum]
                self.min_is_param = True
            self.maximum = maximum
            if maximum in params:
                self.maximum = params[maximum]
                self.max_is_param = True

    @staticmethod
    def read(file_name, params):
        """
        Read the samples from a CSV file
        """
        try:
            fp = io.open(file_name)
        except IOError as e:
            sys.stderr.write("Error opening file %s: %s\n"%(file_name, e.strerror))
            return False

        header = fp.readline().strip()

        samples = []
        sample_map = {}
        for line in fp:
            line = line.strip()
            words = line.split(",")
            if words[0] in params:
                param = params[words[0]]
                new_sample = Sample(param, words[1], words[2], words[3], words[4], params)
                samples.append(new_sample)
                sample_map[words[0]] = new_sample
            else:
                sys.stderr.write("Warning: parameter %s ignored as it is not in the model\n" % words[0])

        fp.close()

        for sample in samples:
            if sample.min_is_param and sample.minimum.varname in sample_map:
                sample.minimum = sample_map[sample.minimum.varname]
            if sample.max_is_param and sample.maximum.varname in sample_map:
                sample.maximum = sample_map[sample.maximum.varname]

        return samples

    def minimumValue(self):
        self.tagged = True
        retval = None
        if self.minimum == "NA":
            retval = "NA"
        elif self.one_of:
            retval = 0
        elif isinstance(self.param, Chooser):
            retval = self.minimum
        elif self.min_is_param:
            if isinstance(self.minimum, Parameter):
                retval = self.minimum.value
            elif isinstance(self.minimum, Sample):
                if self.minimum.sampled:
                    retval = self.minimum.last_sample
                else:
                    if self.minimum.tagged:
                        sys.stderr.write("Error! parameter %s has circular references to other parameters\n" % self.param.varname)
                        sys.exit(1)
                    retval = self.minimum.minimumValue()
        else:
            retval = self.minimum
        self.tagged = False
        return retval

    def maximumValue(self):
        self.tagged = True
        retval = None
        if self.maximum == "NA":
            retval = "NA"
        elif self.one_of:
            retval = len(self.options)
        elif isinstance(self.param, Chooser):
            retval = self.maximum
        elif self.max_is_param:
            if isinstance(self.maximum, Parameter):
                retval = self.maximum.value
            elif isinstance(self.maximum, Sample):
                if self.maximum.sampled:
                    retval = self.maximum.last_sample
                else:
                    if self.maximum.tagged:
                        sys.stderr.write("Error! parameter %s has circular references to other parameters\n" % self.param.varname)
                        sys.exit(1)
                    retval = self.maximum.maximumValue()
        else:
            retval = self.maximum
        self.tagged = False
        return retval

    def sample(self):
        """
        Make a random sample of the parameter
        """
        if self.minimum == "NA" or self.maximum == "NA":
            if isinstance(self.param, Chooser):
                self.last_sample = self.param.getOptionValue(self.setting)
            else:
                self.last_sample = self.setting
        elif self.one_of:
            rint = rnd.randint(0, len(self.options))
            self.last_sample = self.options[rint]
        elif self.minimum == self.maximum:
            if isinstance(self.param, Chooser):
                self.last_sample = self.param.getOptionValue(self.maximum)
            elif isinstance(self.minimum, Parameter):
                self.last_sample = self.minimum.value
            else:
                self.last_sample = self.minimum
        else:
            if self.datatype == "integer":
                minm = int(self.minimumValue())
                maxm = int(self.maximumValue())
                rint = rnd.randint(minm, maxm)
                if isinstance(self.param, Chooser):
                    self.last_sample = self.param.getOptionValue(rint)
                else:
                    self.last_sample = rint
            elif self.datatype == "numeric":
                minm = float(self.minimumValue())
                maxm = float(self.maximumValue())
                self.last_sample = rnd.uniform(minm, maxm)
            elif self.datatype == "boolean":
                self.last_sample = (rnd.random() < 0.5)
            else:
                self.last_sample = self.setting

        self.sampled = True
        return self.last_sample

    def newSample(self):
        self.sampled = False

    def regularSample(self, step, step_size):
        """
        Make a regular sample of the parameter
        """
        if self.minimum == "NA" or self.maximum == "NA":
            self.last_sample = self.setting
        elif self.one_of:
            choice = step * step_size
            self.last_sample = self.options[choice]
        elif self.minimum == self.maximum:
            if isinstance(self.param, Chooser):
                self.last_sample = self.param.getOptionValue(self.maximum)
            elif isinstance(self.minimum, Parameter):
                self.last_sample = self.minimum.value
            else:
                self.last_sample = self.minimum
        else:
            choice = step * step_size
            if self.datatype == "integer":
                choice = int(choice)
                if isinstance(self.param, Chooser):
                    self.last_sample = self.param.getOptionValue(choice)
                elif isinstance(self.minimum, Parameter):
                    self.last_sample = int(self.minimum.value) + choice
                else:
                    self.last_sample = int(self.minimum) + choice
            elif self.datatype == "numeric":
                if instance(self.minimum, Parameter):
                    self.last_sample = float(self.minimum.value) + choice
                else:
                    self.last_sample = self.minimum + choice
            elif self.datatype == "boolean":
                self.last_sample = ((step % 2) == 1)
            else:
                self.last_sample = self.setting
        return self.last_sample


################################################################################
# Batch Class
#
#   ####     #    #####   ####  #   #
#   #   #   # #     #    #      #   #
#   ####   #   #    #    #      #####
#   #   #  #####    #    #      #   #
#   ####   #   #    #     ####  #   #
#
################################################################################

class Batch:
    """
    The Batch class manages batch sizes and tasks, working with Script class
    instances to make sure that names and directories for script files are
    consistent.
    """
    def __init__(self, opts, expts):
        self.n_expt = len(expts)
        self.n_expt_digits = Batch.n_digits(self.n_expt)
        self.xml = opts.arg_xml
        self.task_limit = opts.task_limit
        self.n_batch = 1 if self.n_expt <= opts.max_batch else math.ceil(self.n_expt / opts.batch_size)
        self.n_batch_digits = Batch.n_digits(self.n_batch)
        self.batch_size = self.n_expt if self.n_batch == 1 else opts.batch_size

        # Check that the array of experiments has a predictable nomenclature
        # that includes all the numbers from 1 to n_expt inclusive with no
        # duplicates
        self.expt_name = expts[1].name
        expt_names = {}
        self.n_runs = 0
        for expt in expts:
            if expt.name in expt_names:
                raise NLogoError("Duplicate experiment name \"{name}\"".format(name = expt.name),
                    bug = True)
            expt_names[expt.name] = 1
            self.expt_name = os.path.commonprefix([expt.name, self.expt_name])
            self.n_runs += expt.getNRuns()

        if self.expt_name == "":
            raise NLogoError("No common experiment name nomenclature", bug = True)

        for i in range(self.n_expt):
            id = "%0*d"%(self.n_expt_digits, i + 1)
            expected_name = "{x}{n}".format(x = self.expt_name, n = id)
            if not expected_name in expt_names:
                raise NLogoError(
                    "Not found expected experiment name \"{name}\"".format(name = expected_name),
                    bug = True)

        self.script = Script(opts, self.n_expt, self)


    @staticmethod
    def n_digits(n):
        return len("%d"%(n))

    @staticmethod
    def outdir(opts, expt_name, expt_i, expt_n):
        n_batch = 1 if expt_n <= opts.max_batch else math.ceil(expt_n / opts.batch_size)
        n_batch_digits = Batch.n_digits(n_batch)
        n_expt_digits = Batch.n_digits(expt_n)
        batch_size = expt_n if n_batch == 1 else opts.batch_size
        batch_n = math.ceil(expt_i / batch_size)
        x = opts.arg_xml[:-4]

        if n_batch == 1:
            if opts.sep_expt_dirs:
                return opts.dir + "/%s-%0*d"%(expt_name, n_expt_digits, expt_i)
            else:
                return opts.dir
        else:
            if opts.sep_expt_dirs:
                return opts.dir + "/%s-%0*d/%s-%0*d"%(x, n_batch_digits, batch_n, expt_name, n_expt_digits, expt_i) 
            else:
                return opts.dir + "/%s-%0*d"%(x, n_batch_digits, batch_n)

    def getTaskIDSh(self, task_var):
        return u'''
TASK_NO={var}
if [[ "$#" -gt 0 ]]
then
  TASK_NO=$(expr $TASK_NO + $1)
fi
if [[ TASK_NO -gt {n} ]]
then
  exit
fi
'''.format(var = task_var, n = self.n_expt)

    def getBatchIDSh(self):
        if self.n_batch == 1:
            return u"# No BATCH_ID this experiment\nXML={x}\nBDIR=.\n".format(x = self.xml)
        else:
            return u'''
BATCH_NO=$(expr $TASK_NO / {size})
if [[ $(expr $TASK_NO % {size}) -gt 0 ]]
then
  BATCH_NO=$(expr $BATCH_NO + 1)
fi
printf -v BATCH_ID "%0{n}d" $BATCH_NO
XML="{x}-$BATCH_ID.xml"
BDIR="{x}-$BATCH_ID"
'''.format(size = self.batch_size, n = self.n_batch_digits, x = self.xml[:-4])

    def dupSetupSh(self, opts):
        sh = "test -d \"$RDIR/$EXPT_ID\" || mkdir -p \"$RDIR/$EXPT_ID\"\n"
        for ln in opts.dup_links:
            s = "`pwd`/" + ln
            d = "$RDIR/$EXPT_ID/" + ln[(1 + ln.rfind("/")):]
            sh += "if [[ ! -e \"{dest}\" ]]\nthen\n  if [[ -d \"{src}\" ]]\n  then\n    ln -s \"{src}\" \"{dest}\"\n  else\n    ln \"{src}\" \"{dest}\"\n  fi\nfi\n".format(src = s, dest = d)
        return sh

    def getExptIDsh(self):
        return u'''
printf -v EXPT_ID "{name}%0{n}d" $TASK_NO
'''.format(name = self.expt_name, n = self.n_expt_digits)

    def saveSGE(self, file_name):
        self.script.saveSGE(file_name)

    def saveSLURM(self, file_name):
        self.script.saveSLURM(file_name)

################################################################################
# Script Class
#
#    ####   ####  ####   ###  ####   #####
#   #      #      #   #   #   #   #    #
#    ###   #      ####    #   ####     #
#       #  #      #   #   #   #        #
#   ####    ####  #   #  ###  #        #
#
################################################################################

class Script:
    """
    The script class writes the SLURM and/or SGE script to run the job on a
    cluster. (SGE will increasingly not be maintained.) This is complicated
    by various considerations to do with threading, cores, garbage collection,
    and workarounds for job size limits.
    """
    def __init__(self, opts, n_expt, batch):
        self.opts = opts
        self.dir = opts.dir
        self.n_expt = n_expt
        self.name = opts.jobname if opts.jobname != "" else opts.arg_xml[:-4]
        self.gigaram = opts.gigaram if opts.limit_ram else 0
        self.concur = opts.concur if opts.concur <= n_expt else n_expt
        self.time = int(opts.days * 86400)
        self.need_sleeper = (opts.task_limit > 0 and opts.task_limit < n_expt)
        self.task_size = opts.task_limit if self.need_sleeper else n_expt
        self.batch = batch

    def saveSGE(self, file_name):
        """
        Save a Sun Grid Engine job submission script
        """
        if self.need_sleeper:
            sleeper_script = file_name
            file_name = "%s-%d.sh" % (file_name[:file_name.rfind(".")], self.opts.task_limit)
            self.saveSleeperScript(sleeper_script, file_name)
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            raise NLogoError("Error creating file \"{name}\"".format(file_name), cause = e)
        fp.write(u'''#!/bin/sh
#$ -cwd
#$ -t 1-{ntask}
#$ -pe smp {svr_cores}
#$ -N {name}
#$ -l h_cpu={time}
'''.format(ntask = self.task_size, svr_cores = self.opts.cores(), name = self.name,
            time = self.time))
        if self.concur != 0:
            fp.write(u"#$ -tc {concur}\n".format(concur = self.concur))
        if self.opts.out != "":
            fp.write(u"#$ -o {out}\n".format(out = self.opts.out))
        if self.opts.err != "":
            if self.opts.err == self.opts.out:
                fp.write(u"#$ -j y\n")
            else:
                fp.write(u"#$ -e {err}\n".format(err = self.opts.err))
        if self.opts.project != "":
            fp.write(u"#$ -P {proj}\n".format(proj = self.opts.project))

        if self.gigaram != 0:
            fp.write(u"#$ -l h_vmem={mem}m\n".format(mem = int(self.gigaram * 1024 / self.opts.cores())))
        
        fp.write(self.batch.getTaskIDSh("$SGE_TASK_ID"))
 
        self.saveCommon(fp, self.opts.getNanny())
        fp.close()
        os.chmod(file_name, 0o755)

    def saveSLURM(self, file_name):
        """
        Save a SLURM job submission script
        """
        if self.need_sleeper:
            sleeper_script = file_name
            file_name = "%s-%d.sh" % (file_name[:file_name.rfind(".")], self.opts.task_limit)
            self.saveSleeperScript(sleeper_script, file_name)
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            raise NLogoError("Error creating file \"{name}\"".format(file_name), cause = e)
        fp.write(u"#!/bin/sh\n")
        if self.opts.wait == 0:
            fp.write(u"#SBATCH --begin=now\n")
        else:
            fp.write(u"#SBATCH --begin=now+{wait}\n".format(wait = self.opts.wait))
        fp.write(u"#SBATCH --cpus-per-task={cores}\n#SBATCH --job-name={name}\n".format(
            cores = self.opts.cores(), name = self.name))
        if self.time != 0:
            fp.write(u"#SBATCH --time={time}\n".format(time = math.ceil(self.time / 60)))
        if self.opts.out != "":
            fp.write(u"#SBATCH --output={out}\n".format(out = self.opts.out))
        if self.opts.err != "":
            fp.write(u"#SBATCH --error={err}\n".format(err = self.opts.err))
        if self.concur != 0:
            fp.write(u"#SBATCH --array=1-{ntask}%{concur}\n".format(
                ntask = self.task_size, concur = self.concur))
        else:
            fp.write(u"#SBATCH --array=1-{ntask}\n".format(ntask = self.task_size))
        if self.opts.project != "":
            fp.write(u"#SBATCH --wckey={proj}\n".format(proj = self.opts.project))
        if self.gigaram != 0:
            fp.write(u"#SBATCH --mem-per-cpu={mem}\n".format(
                mem = int(self.gigaram * 1024 / self.opts.cores()))
            )
        fp.write(self.batch.getTaskIDSh("$SLURM_ARRAY_TASK_ID"))

        if self.opts.unique_home:
            fp.write(u"tmphome=`mktemp -d \"/var/tmp/{name}-HOME-$TASK_NO-XXXXXX\"`\n")
        submit_cmd = "srun "
        if self.opts.unique_home:
            submit_cmd = "HOME=\"$tmphome\" $SHELL <<TMPHOMESH\nsrun "
        self.saveCommon(fp, submit_cmd + self.opts.getNanny())
        if self.opts.unique_home:
            fp.write(u"\nTMPHOMESH\nsleep 5 # Paranoia\n/bin/rm -rf \"$tmphome\"\n")
        fp.close()
        os.chmod(file_name, 0o755)

    def saveCommon(self, fp, cmd = ""):
        """
        Save parts of the job submission script common to SLURM and SGE
        """
        fp.write(self.batch.getBatchIDSh())
        fp.write(self.batch.getExptIDsh())

        if self.opts.delay != 0:
            fp.write(u"sleep $((RANDOM % {delay}))\n".format(delay = self.opts.delay))
        if self.dir != '.':
            fp.write(u"RDIR=\"`pwd`/{dir}/$BDIR\"\n".format(dir = self.dir))
        else:
            fp.write(u"RDIR=\"`pwd`/$BDIR\"\n")

        if self.opts.sep_expt_dirs:
            if self.opts.dup_setup:
                fp.write(self.batch.dupSetupSh(self.opts))
            fp.write(u"RDIR=\"$RDIR/$EXPT_ID\"\n")
        fp.write(u"test -d \"$RDIR\" || mkdir -p \"$RDIR\"\n")

        if self.opts.dup_setup:
            fp.write(u"MDIR=\"$RDIR\"\n")
        else:
            if self.opts.model_dir == ".":
                fp.write(u"MDIR=\"`pwd`\"\n")
            else:
                fp.write(u"MDIR=\"`pwd`/{dir}\"\n".format(dir = self.opts.model_dir))

        if self.opts.xml_dir == ".":
            fp.write(u"XDIR=\"`pwd`\"\n")
        else:
            fp.write(u"XDIR=\"`pwd`/{dir}\"\n".format(dir = self.opts.xml_dir))

        fp.write(u'''
export JAVA_HOME="{java_home}"
cd "{nlogo_home}"
OUT="$RDIR/$EXPT_ID.out"
CSV="$RDIR/$EXPT_ID-table.csv"
{cmd} "{nlogo_invoke}" --model "$MDIR/{model}" --setup-file "$XDIR/$XML" --experiment "$EXPT_ID" --threads {nlogo_threads} --table "$CSV" > "$OUT" 2>&1
'''.format(java_home = self.opts.java,
            nlogo_home = self.opts.nlogoHome(), cmd = cmd,
            nlogo_invoke = self.opts.invokePath(), model = self.opts.model,
            nlogo_threads = self.opts.threads))
        if self.opts.zip:
            fp.write(u"test -e \"$OUT\" && gzip \"$OUT\"\n")
            fp.write(u"test -e \"$CSV\" && gzip \"$CSV\"\n")

    def saveSleeperScript(self, file_name, batch_script):
        """
        A sleeper script is needed when the task/array size limit is exceeded
        by the number of runs. This script runs in the background (nohupped,
        niced) and waits for an array to finish before automatically submitting
        the next array of jobs.
        """
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            raise NLogoError("Error creating file \"{name}\"}".format(name = file_name), cause = e)
        fp.write(u"#!/bin/sh\n")
        fp.write(u"me=`whoami`\n")

        nsleep = math.ceil(self.n_expt / self.opts.task_limit)
        fp.write(u"for n in `seq 0 {s}`\n".format(s = nsleep - 1))
        fp.write(u"do\n")

        subscr = "qsub" if self.opts.cluster == "SGE" else "sbatch"
        proj = "-P " if self.opts.cluster == "SGE" else "--wckey="
        prid = "$1" if self.opts.project == "" else self.opts.project
        fp.write(u"  {sub} {pj}{pd} {s} `expr $n \\* {n}`\n".format(
            sub = subscr, pj = proj, pd = prid, s = batch_script,
            n = self.opts.task_limit
        ))
        fp.write(u"  echo \"Submitted {expt} $n\"\n".format(expt = self.name))
        fp.write(u"  sleep 600 # wait 10 minutes to make sure job in\n")
        qlist = "qstat" if self.opts.cluster == "SGE" else "squeue"
        fp.write(u"  while [[ \"`{q} | grep $me | wc -l`\" -gt 0 ]]\n".format(
            q = qlist
        ))
        fp.write(u"  do\n")
        fp.write(u"    sleep \"`expr $RANDOM % 1800`\" # random time < 0.5h\n")
        fp.write(u"  done\n")
        fp.write(u"done\n")
        fp.close()
        os.chmod(file_name, 0o755)

    @staticmethod
    def saveProgressScript(file_name, opts):
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            raise NLogoError("Error creating progress script \"{name}\"".format(name = file_name), cause = e)
        
        fp.write('''
#!/usr/bin/perl
''')
        fp.close()
        os.chmod(file_name, 0o755)

################################################################################
# Option Class
#
#    ###   ####   #####  ###   ###   #   #
#   #   #  #   #    #     #   #   #  ##  #
#   #   #  ####     #     #   #   #  # # #
#   #   #  #        #     #   #   #  #  ##
#    ###   #        #    ###   ###   #   #
#
################################################################################

class Option:
    options = {}

    def __init__(self, long_name, help_text, default,
                 once = True, args = [], cmd = [], short_name = "", mutex = [], prereq = []):
        self.long_name = long_name
        self.help_text = help_text
        self.default = default
        self.args = args
        self.n_args = len(args)
        if self.n_args == 0 and not once:
            sys.stderr.write("BUG! Option {o} is a flag that can be set more than once".format(o = opt))
            sys.exit(1)

        self.cmd = cmd
        self.short_name = short_name
        self.once = once
        self.mutex = mutex
        self.prereq = prereq
        self.values = []
        Option.addOption(self)

    @staticmethod
    def assigned(opt):
        if "--" + opt in Option.options:
            return len(Option.options["--" + opt].values) > 0
        else:
            sys.stderr.write("BUG! Option {o} not in dict".format(o = opt))
            sys.exit(1)

    @staticmethod
    def getFlag(opt):
        if "--" + opt in Option.options:
            the_opt = Option.options["--" + opt]
            if the_opt.n_args != 0:
                sys.stderr.write("BUG! Option {o} is not a flag".format(o = opt))
                sys.exit(1)

            if len(the_opt.values) == 1:
                # The user has assigned the flag a value
                return parseBoolean(the_opt.valueStr())
            else:
                # The user has not assigned the flag a value...
                if len(the_opt.mutex) == 1:
                    # ... check if the mutually-exclusive flag has
                    # been assigned a value ...
                    mutex_opt_str = "--" + the_opt.mutex[0]
                    if mutex_opt_str in Option.options:
                        mutex_opt = Option.options[mutex_opt_str]
                        if len(mutex_opt.values) > 0:
                            # The user has assigned the mutex flag a value
                            return not parseBoolean(mutex_opt.valueStr())
                # ... before (effectively) returning the default
                return parseBoolean(the_opt.valueStr())
        else:
            sys.stderr.write("BUG! Option {o} not in dict".format(o = opt))
            sys.exit(1)

    @staticmethod
    def printSummary(cmd):
        for k in sorted(Option.options.keys()):
            if k[:2] == "--":
                opt = Option.options[k]
                val = opt.valueStr()
                if len(opt.cmd) == 0 or cmd in opt.cmd:
                    if(opt.once):
                        if(opt.n_args == 0):
                            if val == "":
                                print("{o} has not been set".format(o = opt.long_name))
                            else:
                                print("{o} is {v}".format(o = opt.long_name, v = val))
                        elif(opt.n_args == 1):
                            if val == "":
                                print("{o} has no value for {a}".format(o = opt.long_name, a = opt.args[0]))
                            else:
                                print("{o} has {a} = {v}".format(o = opt.long_name, a = opt.args[0], v = val))
                        else:
                            for i in range(len(opt.args)):
                                print("{o} has {a} = {v}".format(o = opt.long_name, a = opt.args[i], v = val[i]))
                    elif len(val) > 0:
                        print("{o} has the following values:".format(o = opt.long_name))
                        for i in range(len(val)):
                            print("\t{n}. {v}".format(n = i + 1, v = val[i]))
                    else:
                        print("{o} has no values".format(o = opt.long_name))


    def assign(self, value):
        if self.once and len(self.values) > 1:
            sys.stderr.write("You cannot use option {o} more than once\n".format(o = self.long_name))
            sys.exit(1)
        for opt in self.mutex:
            if Option.assigned(opt):
                sys.stderr.write("You cannot use option {o} if you've already used option {p}\n".format(
                    o = self.long_name, p = opt))
                sys.exit(1)
        for opt in self.prereq:
            if not Option.assigned(opt):
                sys.stderr.write("Option {o} requires a value to have been set for option {p}\n".format(
                    o = self.long_name, p = opt))
                sys.exit(1)
        self.values.append(value)

    def valueStr(self):
        if len(self.values) == 0:
            return str(self.default)
        elif self.once and self.n_args <= 1:
            return str(self.values[0])
        else:
            return self.values

    def getHelp(self):
        helpstr = "--" + self.long_name
        if self.short_name != "":
            helpstr += "/-" + self.short_name
        for arg in self.args:
            helpstr += " <" + arg + ">"
        helpstr += ": " + self.help_text
        if self.default != "":
            helpstr += " (default \"" + str(self.default) + "\")"
        return helpstr

    @staticmethod
    def parseOptions(args):
        Option.initOptions()
        i = 1
        while i < len(args) and args[i][0] == "-":
            opt = Option.get(args[i])
            i += 1
            if opt == None:
                break
            else:
                if opt.n_args == 0:
                    opt.assign(True)
                elif opt.n_args == 1:
                    opt.assign(args[i])
                    i += 1
                else:
                    assigment = []
                    for j in range(0, opt.n_args):
                        assignment.append(args[i + j])
                    opts.assign(assigment)
                    i += opt.n_args
        return i

    @staticmethod
    def printHelp(prefix = ""):
        for opt in sorted(Option.options.keys()):
            if opt[:2] == "--":
                for line in lineBreak(prefix + Option.options[opt].getHelp(), "\t"):
                    print(line)
        print(prefix + "--: end options")

    @staticmethod
    def get(str):
        if str in Option.options:
            return Option.options[str]
        elif "-" + str in Option.options:
            return Option.options["-" + str]
        elif "--" + str in Option.options:
            return Option.options["--" + str]
        elif str == "--":
            return None
        else:
            sys.stderr.write("Option \"{opt}\" not recognized\n".format(opt = str))
            sys.exit(1)

    @staticmethod
    def addOption(opt):
        if opt.long_name in Option.options:
            sys.stderr.write("BUG! Duplication of long option \"{l}\"\n".format(o = opt.long_name))
            sys.exit(1)
        Option.options["--" + opt.long_name] = opt
        if opt.short_name != "":
            if len(opt.short_name) != 1:
                sys.stderr.write("Short name \"{o}\" is too long\n".format(o = opt.short_name))
                sys.exit(1)
            if opt.short_name in Option.options:
                sys.stderr.write("Duplication of short option \"{o}\"\n".format(o = opt.short_name))
                sys.exit(1)
            Option.options["-" + opt.short_name] = opt

    @staticmethod
    def scriptCmds():
        return ["montq", "splitq"]

    @staticmethod
    def exptCmds():
        return ["monte", "split", "montq", "splitq"]

    @staticmethod
    def initOptions():
        # short_name taken records: # means option taken
        # abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ
        #  # ######### ###  ###### ### # ### # # ###  ###    #   
        Option("add-outdir", "add the output directory to the beginning of " +
            "any parameter given with --file-param", False, cmd = Option.exptCmds(),
             prereq = ["file-param"])
        Option("batch-max", "maximum number of experiments to save in one XML file; " +
            "the XML parser used in some versions of NetLogo can slow down " +
            "significantly if this is more than 10000 (the default) or so. The " +
            "script and experiment files will be split up into batches of size " +
            "batch-size", 10000, args = ["n"], cmd = Option.exptCmds(), short_name = "b")
        Option("batch-size", "if batch-max exceeded, experiments to save per XML " +
            "file (should be less than or equal to batch-max, obvs.)", 5000, args = ["n"],
            cmd = Option.exptCmds(), short_name = "B")
        Option("dir", "directory to save results to. If you're making lots of runs, " +
            "this can be a good way of keeping things tidy in your top-level model " +
            "directory", ".", args = ["dir"], cmd = Option.exptCmds(), short_name = "d")
        Option("dir-param", "specify the name of a parameter in your model that should " +
            "be set to the results directory given with the --dir argument. If there " +
            "are several such parameters, then this argument can be reused", "",
            once = False, args = ["param"], cmd = Option.exptCmds())
        Option("dup-setup", "duplicate the setup (entails --sep-expt-dirs) using hard " +
            "links", False, cmd = Option.exptCmds(), short_name = "D", prereq = ["dir"])
        Option("dup-setup-omit", "omit files and/or directories from duplicate setup links " +
            "(by default everything in the same directory as the model will be included " +
            "unless this script expects it to be created by running the model -- use this " + 
            "option to specifically exclude things) ", "", once = False,
            args = ["file or dir"], mutex = ["dup-setup-add"], prereq = ["dup-setup"],
            cmd = Option.exptCmds(), short_name = "O")
        Option("dup-setup-add", "add files and/or directories from duplicate setup links " +
            "(using this option, only the model file will be linked, and you can add other " +
            "files or directories that need linking)", "", once = False,
            args = ["file or dir"], mutex = ["dup-setup-omit"], prereq = ["dup-setup"],
            cmd = Option.exptCmds(), short_name = "A")
        Option("error", "file to save job submission script error stream to " +
            "(output and error from the NetLogo command will be saved elsewhere)",
            "/dev/null", args = ["file"], cmd = Option.scriptCmds(), short_name = "e")
        Option("expt-dir", "directory to save experiment XML files to", ".",
            args = ["dir"], cmd = Option.exptCmds(), short_name = "E")
        Option("file-param", "specify the name of a parameter in your model that " +
            "should be set to a unique name in the experiment configuration", "",
            once = False, args = ["param"], cmd = Option.exptCmds())
        Option("find-netlogo", "where to find NetLogo", "/mnt/apps/netlogo",
            cmd = Option.scriptCmds(), short_name = "f")
        Option("gibibytes", "amount of RAM expected to be needed to run the model " +
            "(adjusts the invocation script used and hard memory limits in the job " +
            "submission script; use --no-limit-ram if you don't want the latter)", 4,
            args = ["n"], cmd = Option.scriptCmds(), short_name = "g")
        Option("go", "use the given code as the go command rather than whatever " +
            "is found in the go button (monte-carlo experiments only)", "", args = ["code"],
            cmd = ["montq", "monte"])
        Option("help", "print this message and exit", False, short_name = "h")
        Option("headless", "use the default netlogo-headless.sh to invoke NetLogo",
            False, cmd = Option.scriptCmds(), short_name = "H")
        Option("invoke-netlogo", "use the specified NetLogo invocation script", "",
            args = ["exe"], cmd = Option.scriptCmds(), short_name = "i")
        Option("java", "where to find the JAVA Virtual Machine (dir/bin/java)",
            os.getenv("JAVA_HOME", "/mnt/apps/java/jdk-17.0.1"), args = ["dir"],
            cmd = Option.scriptCmds(), short_name = "j")
        Option("job-name", "identifier to use for the job's name on the cluster " +
            "(defaults to the name of the experiment file)", "", args = ["name"],
            cmd = Option.scriptCmds(), short_name = "J")
        Option("kill-days", "if the run isn't finished in n days, kill it; use 0 " +
            "to let it run indefinitely", 1, args = ["n"], cmd = Option.scriptCmds(),
            short_name = "k")
        Option("limit-concurrent", "limit the number of concurrent runs on the " +
            "cluster; can be useful if this will be a long-running job and you want " +
            "to submit other stuff while this is running", 0, args = ["n"],
            cmd = Option.scriptCmds(), short_name = "l")
        Option("mc-expt", "experiment name stem to use for monte and montq " +
            "commands", "x", args = ["name"], cmd = ["monte", "montq"], short_name = "x")
        Option("nanny", "use the 'childminder' program to monitor the model runs; see " +
            "https://github.com/garypolhill/nanny", False, cmd = Option.scriptCmds(),
            short_name = "n", mutex = ["no-nanny"])
        Option("no-final-save", "don't save the parameters and metrics to a CSV file as " +
            "an added 'final' command", False, cmd = Option.exptCmds(), short_name = "F")
        Option("no-limit-ram", "don't use --gibibytes to limit the RAM in the job " +
            "submission script", False, cmd = Option.scriptCmds(), short_name = "G")
        Option("no-nanny", "don't use the 'childminder' program", True, cmd = Option.scriptCmds(),
            short_name = "N", mutex = ["nanny"])
        Option("no-progress", "don't add progress files to experiments", False,
            cmd = Option.exptCmds(), short_name = "P")
        Option("no-task-limit", "your cluster has no limit to the number of tasks in a job " +
            "submission script", False, cmd = Option.scriptCmds(), mutex = ["task-limit"])
        Option("no-unique-home", "do not use a unique $HOME for each run", False,
            mutex = ["unique-home"], short_name = "U", cmd = Option.scriptCmds())
        Option("no-zip", "don't gzip the output file and table CSV file after the " +
            "NetLogo run has finished", True, cmd = Option.scriptCmds(), short_name = "z",
            mutex = ["zip"])
        Option("output", "file to save job submission script output stream to " +
            "(output and error from the NetLogo command will still be saved)",
            "/dev/null", args = ["file"], cmd = Option.scriptCmds(), short_name = "o")
        Option("project", "project to charge (in the script); in SGE this " +
            "sets the -P option in the job submission script; in SLURM the --wckey",
            "", args = ["project"], cmd = Option.scriptCmds(), short_name = "p")
        Option("rng-no-switch", "specify the name of a parameter in your model " +
            "that must be set to 'false' to get a new random seed for each run",
            "", args = ["param"], cmd = Option.exptCmds(), mutex = ["rng-switch"])
        Option("rng-param", "specify the name of a parameter in which the RNG seed " +
            "is stored in your model -- this will be added to the metrics", "",
            args = ["param"], cmd = Option.exptCmds())
        Option("rng-switch", "specify the name of a parameter in your model that " +
            "must be set to 'true' to get a new random seed for each run", "",
            args = ["param"], cmd = Option.exptCmds(), mutex = ["rng-no-switch"])
        Option("sep-expt-dirs", "use separate directories for each (split) experiment",
            False, cmd = Option.exptCmds(), short_name = "S")
        Option("setup", "use the given code to set up rather than what is found in " +
            "the setup button (Monte Carlo experiments only)", "", args = ["code"],
            cmd = ["monte", "montq"])
        Option("SGE", "create a Sun Grid Engine submission script", False,
            cmd = Option.scriptCmds(), mutex = ["SLURM"])
        Option("sleep-random", "each run should sleep random max n seconds before " +
            "starting; this can be a good idea to stop hundreds of processes trying " +
            "to access the same files at the same time", 0, args = ["n"],
            cmd = Option.scriptCmds(), short_name = "s")
        Option("SLURM", "create a SLURM submission script", True,
            cmd = Option.scriptCmds(), mutex = ["SGE"])
        Option("split-reps", "with the split and splitq commands, also split repetitions " +
            "of parameter settings in the experiment", False, cmd = ["split", "splitq"])
        Option("task-limit", "maximum size of a job array (or number of tasks) that " +
            "can be submitted from a single script", 1000, args = ["n"],
            cmd = Option.scriptCmds(), short_name = "L", mutex = ["no-task-limit"])
        Option("threads", "use n threads in each simulation run for running the " +
            "model; recommend 1 (the default), but this will be passed in the " +
            "--threads option to NetLogo and affects the number of cores that will " +
            "be requested for the run (with --threads-gc)", 1, args = ["n"],
            cmd = Option.scriptCmds(), short_name = "t")
        Option("threads-gc", "use n garbage collection threads (>= 2)", 3,
            args = ["n"], cmd = Option.scriptCmds(), short_name = "T")
        Option("unique-home", "use a unique home directory for each run", True,
            mutex = ["no-unique-home"], short_name = "u", cmd = Option.scriptCmds())
        Option("version", "NetLogo version to use (e.g. 6.2.1)", "6.2.2",
            args = ["version"], cmd = Option.scriptCmds(), short_name = "v")
        Option("wait", "(SLURM only) queue n seconds from sbatch submission", 0,
            args = ["n"], cmd = Option.scriptCmds(), short_name = "w")
        Option("zip", "do gzip the output file and table CSV file after the NetLogo run " +
            "has finished (and save space)", False, cmd = Option.scriptCmds(),
            short_name = "Z", mutex = ["no-zip"])

################################################################################
# Options Class
#
#    ###   ####   #####  ###   ###   #   #   ####
#   #   #  #   #    #     #   #   #  ##  #  #
#   #   #  ####     #     #   #   #  # # #   ###
#   #   #  #        #     #   #   #  #  ##      #
#    ###   #        #    ###   ###   #   #  ####
#
################################################################################

class Options:
    def __init__(self, args):
        i = Option.parseOptions(args)

        if Option.assigned("help"):
            Options.help()

        # Assign options from parsed command-line options/defaults

        self.add_outdir = Option.getFlag("add-outdir")
        self.max_batch = int(Option.get("batch-max").valueStr())
        self.batch_size = int(Option.get("batch-size").valueStr())
        self.dir = Option.get("dir").valueStr()
        self.dir_params = Option.get("dir-param").valueStr()
        self.dup_setup = Option.getFlag("dup-setup")
        self.err = Option.get("error").valueStr()
        self.xml_dir = Option.get("expt-dir").valueStr()
        self.file_params = Option.get("file-param").valueStr()
        self.nlogo_home = Option.get("find-netlogo").valueStr()
        self.gigaram = int(Option.get("gibibytes").valueStr())
        self.go = Option.get("go").valueStr()
        self.user_go = Option.assigned("go")
        self.limit_ram = not Option.getFlag("no-limit-ram")
        if Option.getFlag("headless"):
            self.nlogo_invoke = "netlogo-headless.sh"
        else:
            self.nlogo_invoke = Option.get("invoke-netlogo").valueStr()
        self.java = Option.get("java").valueStr()
        self.jobname = Option.get("job-name").valueStr()
        self.days = float(Option.get("kill-days").valueStr())
        self.concur = int(Option.get("limit-concurrent").valueStr())
        self.nanny = Option.getFlag("nanny")
        self.save_csv = not Option.getFlag("no-final-save")
        self.progress = not Option.getFlag("no-progress")
        if Option.assigned("no-task-limit"):
            self.task_limit = 0
        else:
            self.task_limit = int(Option.get("task-limit").valueStr())
        self.out = Option.get("output").valueStr()
        self.project = Option.get("project").valueStr()
        self.rng_switch = Option.get("rng-switch").valueStr()
        self.rng_no_switch = Option.get("rng-no-switch").valueStr()
        self.rng_param = Option.get("rng-param").valueStr()
        self.delay = int(Option.get("sleep-random").valueStr())
        self.setup = Option.get("setup").valueStr()
        self.user_setup = Option.assigned("setup")
        self.cluster = "SLURM"
        if parseBoolean(Option.get("SLURM").valueStr()):
            self.cluster = "SLURM" # Deliberate reimplementation in case default changes
        elif parseBoolean(Option.get("SGE").valueStr()):
            self.cluster = "SGE"
        self.sep_expt_dirs = Option.getFlag("sep-expt-dirs")
        self.split_reps = Option.getFlag("split-reps")
        self.threads = int(Option.get("threads").valueStr())
        self.gc = int(Option.get("threads-gc").valueStr())
        self.nlogov = Option.get("version").valueStr()
        if not Option.assigned("find-netlogo"):
            self.nlogo_home = self.nlogo_home + "-" + self.nlogov
        if not Option.assigned("invoke-netlogo") and not Option.assigned("headless"):
            if Options.cmpver(self.nlogov, "6.2.1") < 0:
                self.nlogo_invoke = "netlogo-headless-{cores}cpu-{gig}g.sh".format(
                    cores = self.cores(), gig = self.gigaram)
            else:
                self.nlogo_invoke = "netlogo-headless-{gc}gc-{gig}Gi.sh".format(
                    gc = self.gc, gig = self.gigaram)
        self.unique_home = Option.getFlag("unique-home")
        self.wait = int(Option.get("wait").valueStr())
        self.name = Option.get("mc-expt").valueStr()
        self.zip = Option.getFlag("zip")

        # Parse command-line arguments

        self.model = args[i]
        self.model_file = self.model
        self.model_dir = "."
        if "/" in self.model:
            self.model_dir = self.model[:(rfind(self.model, "/") - 1)]
            self.model = self.model[(rfind(self.model, "/") + 1)]
        i += 1
        self.cmd = args[i]
        i += 1
        self.cmd_args = []
        self.arg_xml = ""
        self.arg_sh = ""
        while i < len(args):
            self.cmd_args.append(args[i])
            i += 1
        if self.cmd == "param":
            if len(self.cmd_args) == 0:
                self.cmd_args.append("{stem}.csv".format(stem = self.model[0:-6]))
        elif self.cmd == "expts":
            None
        elif self.cmd == "split":
            if len(self.cmd_args) == 1:
                self.cmd_args.append("{stem}.xml".format(stem = self.cmd_args[0]))
            elif len(self.cmd_args) == 0:
                sys.stderr.write("split needs at least one argument\n")
                sys.exit(1)
            self.arg_xml = self.cmd_args[-1]
        elif self.cmd == "splitq":
            if len(self.cmd_args) == 1:
                self.cmd_args.append("{stem}.xml".format(stem = self.cmd_args[0]))
                self.cmd_args.append("{stem}.sh".format(stem = self.cmd_args[0]))
            elif len(self.cmd_args) == 2:
                self.cmd_args.append("{stem}.sh".format(stem = self.cmd_args[1][0:-4]))
            elif len(self.cmd_args) == 0:
                sys.stderr.write("splitq needs at least one argument\n")
                sys.exit(1)
            self.arg_sh = self.cmd_args[-1]
            self.arg_xml = self.cmd_args[-2]
        elif self.cmd == "monte":
            if len(self.cmd_args) == 3:
                self.cmd_args.append("{stem}.xml".format(stem = self.cmd_args[0][0:-4]))
            elif len(self.cmd_args) < 3:
                sys.stderr.write("monte needs at least three arguments\n")
                sys.exit(1)
            self.arg_xml = self.cmd_args[-1]
        elif self.cmd == "montq":
            if len(self.cmd_args) == 3:
                self.cmd_args.append("{stem}.xml".format(stem = self.cmd_args[0][0:-4]))
                self.cmd_args.append("{stem}.sh".format(stem = self.cmd_args[0][0:-4]))
            elif len(self.cmd_args) == 4:
                self.cmd_args.append("{stem}.sh".format(stem = self.cmd_args[3][0:-4]))
            elif len(self.cmd_args) < 3:
                sys.stderr.write("montq needs at least three arguments\n")
                sys.exit(1)
            self.arg_sh = self.cmd_args[-1]
            self.arg_xml = self.cmd_args[-2]
        elif self.cmd != "__GUI__":
            sys.stderr.write("Command \"{cmd}\" not recognized\n".format(cmd = self.cmd))
            sys.exit(1)

        self.dup_links = []
        if self.dup_setup == True:
            self.sep_expt_dirs = True
            self.get_dup_links(self.model, add = Option.get("dup-setup-add").valueStr(), 
                omit = Option.get("dup-setup-omit").valueStr())

        Option.printSummary(self.cmd) 

    @staticmethod
    def help():
        print("Usage: [options] {cmd} <NetLogo model> <command> <command arguments...>\n".format(cmd = sys.argv[0]))
        print("\toptions (mostly relevant only for commands creating scripts):")

        Option.printHelp("  ")

        print('''
    If you're not using The James Hutton Institute's agent-based modelling
    cluster, you will probably need to specify --find-netlogo and --java,
    with --headless given to use the default NetLogo headless invocation
    script or --invoke-netlogo to use one of your own. --gibibytes, --nanny,
    --project, --threads-gc and --version will then probably not do anything
    useful. On most clusters, you will want to muck around with the command
    line options to Java to adjust memory and the number of garbage collection
    threads.

    environment variables:

    +   JAVA_HOME: non-default JVM location to use
    +   NETLOGO_HOME: where to find NetLogo
    +   NETLOGO_INVOKE: full path to script to use to invoke NetLogo

    where <command> is one of:

    +   param [<CSV file>]

        Create a CSV file of all the model's parameters (one per row), with
        columns for parameter name, data type, current setting, minimum and
        maximum. If the CSV file is not given, the model name will be used
        to generate it.

    +   expts

        Print the list of names of experiments in the model file

    +   split <experiment name> [<XML file>]

        Take each of the unique parameter settings in the experiment with
        the given name, and create an experiment XML in which each setting
        has its own entry. If the XML file is not given, the experiment name
        will be used to generate it.

    +   splitq <experiment name> [<XML file> [<job submission script>]]

        As per the split command, but also create a job submission shell
        script in the named file allowing each unique parameter setting to be
        run in parallel on a computing cluster. If the XML file is not given,
        the experiment name is used to generate it and the job submission
        script; if the job submission script is not given, the XML file is
        used to generate it.

    +   monte <parameter CSV> <stop step> <n samples> [<XML file>]

        Create an experiment from the NetLogo file in which each of the
        parameters in the parameter CSV file (which you can create with the
        param command) is sampled at random between the specified minimum and
        maximum value (the current setting column is ignored), saving the
        result of the specific number of such samples to the XML file. If the
        XML file is not given the parameter CSV is used to generate it.

    +   montq <parameter CSV> <stop step> <n samples> [<XML file> [<script>]]

        As per the monte command, but then also write a job submission shell
        script in the named file allowing each of the parameter samples to be
        run in parallel on a computing cluster. If the XML file is not given,
        the parameter CSV is used to generate it and the script; if the script
        is not given, the XML file is used to generate it.

To submit the scripts created by splitq and montq, use qsub <script> on Sun
Grid Engine, or sbatch <script> on SLURM. On Hutton machines, if you haven't
used --project to specify in the submission script which account to accumulate
the CPU cycles in, you'll need to do this on the command line with qsub -P
<project> <script> on SGE, or sbatch --wckey=<project> <script> with SLURM.
''')
        sys.exit(0)

    def args(self):
        return self.cmd_args

    def makeBatch(self, expts):
        self.batch = Batch(self, expts)

    @staticmethod
    def cmpver(v1, v2):
        tv1 = v1.split(".")
        tv2 = v2.split(".")
        maxi = min(len(tv1), len(tv2))
        for i in range(maxi):
            if tv1[i].isnumeric() and tv2[i].isnumeric():
                nv1 = int(tv1[i])
                nv2 = int(tv2[i])
                if nv1 < nv2:
                    return -1
                elif nv1 > nv2:
                    return 1
            else:
                if tv1[i] < tv2[i]:
                    return -1
                elif tv1[i] > tv2[i]:
                    return 1
        if len(tv1) < len(tv2):
            return -1
        elif len(tv1) > len(tv2):
            return 1
        else:
            return 0

    def isParamSet(self, param_name):
        if self.rng_switch != "" and self.rng_switch == param_name:
            return True
        elif self.rng_no_switch != "" and self.rng_no_switch == param_name:
            return True
        elif param_name in self.dir_params or param_name in self.file_params:
            return True
        else:
            return False

    def cores(self):
        return self.threads + self.gc

    def nlogoHome(self):
        return self.nlogo_home

    def invokeScript(self):
        if self.nlogo_invoke != "":
            return self.nlogo_invoke
        elif Options.cmpver(self.nlogov, "6.2.1") < 0:
            return "netlogo-headless-{cores}cpu-{gig}g.sh".format(
                cores = self.cores(), gig = self.gigaram)
        else:
            return "netlogo-headless-{gc}gc-{gig}Gi.sh".format(
                gc = self.gc, gig = self.gigaram)

    def invokePath(self):
        return os.getenv("NETLOGO_INVOKE", "{home}/{script}".format(
            home = self.nlogoHome(), script = self.invokeScript()))

    def getNanny(self):
        if self.nanny:
            return os.getenv("NANNY", "/mnt/apps/nanny/childminder")
        else:
            return ""

    def saveScript(self, filename):
        if self.cluster == "SLURM":
            self.batch.saveSLURM(filename)
        elif self.cluster == "SGE":
            self.batch.saveSGE(filename)
        else:
            sys.stderr.write("Cluster format \"{fmt}\" not recognized\n".format(
                fmt = self.cluster))

    def runCmd(self, script, n_expts):
        if self.cluster != "SLURM" and self.cluster != "SGE":
            return script

        prj = "<project>" if self.project == "" else ""
        if n_expts <= self.task_limit:
            cmd = "qsub" if self.cluster == "SGE" else "sbatch"
            qprj = " -P " if self.cluster == "SGE" else " --wckey="
            prj = qprj + prj if self.project == "" else ""
            return "{cmd}{pr} {sh}".format(cmd = cmd, pr = prj, sh = script)
        else:
            prj = " " + prj if self.project == "" else ""
            return "nohup nice ./{sh}{pr} >& <sleeper output> &".format(
                sh = script, pr = prj)

    def setNetLogoModel(self, model_obj):
        self.netlogo_object = model_obj
        parnames = model_obj.getParameterNames()
        if self.rng_param != "" and not self.rng_param in parnames:
            sys.stderr.write("RNG parameter \"{n}\" not in NetLogo file \"{m}\"\n".format(
                n = self.rng_param, m = self.model_file
            ))
            sys.exit(1)
        if self.rng_switch != "" and not self.rng_switch in parnames:
            sys.stderr.write("RNG switch on parameter \"{n}\" not in NetLogo file \"{m}\"\n".format(
                n = self.rng_switch, m = self.model_file
            ))
            sys.exit(1)
        if self.rng_no_switch != "" and not self.rng_switch in parnames:
            sys.stderr.write("RNG switch off parameter \"{n}\" not in NetLogo file \"{m}\"\n".format(
                n = self.rng_no_switch, m = self.model_file
            ))
            sys.exit(1)
        for dirp in self.dir_params:
            if not dirp in parnames:
                sys.stderr.write("Output directory parameter \"{n}\" not in NetLogo file \"{m}\"\n".format(
                    n = dirp, m = self.model_file
                ))
                sys.exit(1)
        for filep in self.file_params:
            if not filep in parnames:
                sys.stderr.write("Output file parameter \"{n}\" not in NetLogo file \"{m}\"\n".format(
                    n = filep, m = self.model_file
                ))
                sys.exit(1)

    def getNetLogoModel(self):
        return self.netlogo_object

    def getSetting(self, parname):
        return self.netlogo_object.getSetting(parname)

    def getUniqueFilename(self, parname, name, run, nruns):
        fname = self.getSetting(parname)
        uname = ""
        nz = 1 + int(math.log10(nruns - 1))

        if self.add_outdir or len(self.dir_params) == 0:
            uname += Batch.outdir(self, name, run, nruns) + "/"

        if fname == "" or fname == "0" or fname == 0 or fname == "NA":
            uname += "%s-%s-%*d" % (name, parname, nz, run)
        else:
            basen = fname
            if "/" in fname:
                # Strip out any existing path in the filename setting
                basen = fname[(1 + fname.rfind("/")):]

            if "." in basen:
                pref = basen[:basen.rfind(".")]
                suff = basen[basen.rfind("."):]
                uname += "%s-%*d.%s" % (pref, nz, run, suff)
            else:
                uname += "%s-%*d" % (basen, nz, run)

        return uname

    def get_dup_links(self, model, add = [], omit = []):
        dir = self.model_dir
        
        if add == "":
            add = []
        if omit == "":
            omit = []
        self.dup_links = [model]
        if len(add) == 0:
            omit.append(self.arg_xml)
            omit.append(self.arg_sh)
            if self.nanny and dir == ".":
                omit.append(dir + "log")
            if self.err != "/dev/null" and dir == ".":
                omit.append(self.err)
            if self.out != "/dev/null" and dir == ".":
                omit.append(self.out)
            if self.dir != ".":
                omit.append(self.dir)
            if self.xml_dir != ".":
                omit.append(self.xml_dir)

        try:
            for file_name in os.listdir(dir):
                if len(add) > 0:
                    if file_name in add:
                        self.dup_links.append(file_name)
                elif len(omit) > 0:
                    if file_name not in omit and file_name[0] != ".":
                        self.dup_links.append(file_name)
                else:
                    raise NLogoError("There should be something to omit at least", bug = True)

        except IOError as e:
            raise NLogoError("Error listing the contents of directory \"" + dir + "\"", cause = e)


################################################################################
# Main
#
#   #   #    #    ###  #   #
#   ## ##   # #    #   ##  #
#   # # #  #   #   #   # # #
#   #   #  #####   #   #  ##
#   #   #  #   #  ###  #   #
#
################################################################################

if __name__ == "__main__":
    opts = Options(sys.argv)

    model = NetlogoModel.read(opts)
    if(model == False):
        sys.exit(1)
    print("Read \"{nlogo}\" from directory \"{dir}\"".format(nlogo = opts.model, dir = opts.model_dir))

    args = opts.args()

    if opts.cmd == 'param':
        model.writeParameters(args[0])
        print("Parameters written to \"{param}\"".format(param = args[0]))
    elif opts.cmd == 'expts':
        model.printExperiments()
    elif opts.cmd == 'split' or opts.cmd == 'splitq':
        expts = model.splitExperiment(args[0], opts)
        if opts.cmd == 'splitq' and len(expts) > 0:
            opts.makeBatch(expts)
            opts.saveScript(args[2])
            print("Job submission script written to \"{sh}\"".format(sh = args[2]))
            print("Submit the script with \"{sub}\"".format(
                sub = opts.runCmd(args[2], len(expts))))
    elif opts.cmd == 'monte' or opts.cmd == 'montq':
        samples = Sample.read(args[0], model.getParameters())
        expt = Experiment.fromWidgets(model.widgets, int(args[1]), opts)
        expts = expt.withNSamples(samples, int(args[2]), opts)
        Experiment.writeExperiments(expts, opts)
        if opts.cmd == 'montq':
            opts.makeBatch(expts)
            opts.saveScript(args[4])
            print("Job submission script written to \"{sh}\"".format(sh = opts.arg_sh))
            print("Submit the script with \"{sub}\"".format(
                sub = opts.runCmd(args[4], len(expts))))

    sys.exit(0)

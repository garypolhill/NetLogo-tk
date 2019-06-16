#!/usr/bin/python
"""nlogo.py
This module contains classes for reading and working with a NetLogo model.
Run from the command line, it can be used to:

* Extract all the parameters from the model's GUI tab into a CSV file
  (This can then be used in a subsequent call to create an experiment)

  ./nlogo.py <nlogo file> param <file to save parameters to>

* Print a list of the experiments from the model's behaviour space

  ./nlogo.py <nlogo file> expt

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
  chunks of, say, 20000 runs at a time.

* Creata a qsub script to run a BehaviorSpace experiment in parallel

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
__version__ = "0.1"
__author__ = "Gary Polhill"

# Imports
import io
import os
import sys
import math
import random as rnd
import xml.etree.ElementTree as xml

# Classes

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

    def variable(self):
        return self.varname

    def settingStr(self):
        return str(self.value)

    def datatypeStr(self):
        return str(self.datatype)

    def setValue(self, value):
        self.value = value

class Output(Widget):
    """
    The Output class is an abstract subclass of Widget containing some output.
    Subclasses include Plot, Monitor and OutputArea
    """
    def __init__(self, type, left, top, right, bottom, display):
        Widget.__init__(self, type, left, top, right, bottom, display, False, True, False)

class Info(Widget):
    """
    The Info class is an abstract subclass of Widget containing information.
    TextBox is the subclass of Info.
    """
    def __init__(self, type, left, top, right, bottom, display):
        Widget.__init__(self, type, left, top, right, bottom, display, False, False, True)

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
        if(fp.readline().strip() == "PENS"):
            penstr = fp.readline().strip()
            while penstr != '':
                plot.addPen(Pen.parse(penstr))
                penstr = fp.readline().strip()

        return plot

    def addPen(self, pen):
        self.pens[pen.display] = pen

    def getPens(self):
        return self.pens.values()

class Pen:
    """
    The Pen class contains data for each pen of a Plot
    """
    def __init__(self, display, interval, mode, colour, in_legend, setup_code,
                 update_code):
        self.display = display
        self.interval = interval
        self.mode = mode
        self.colour = colour
        self.inLegend = in_legend
        self.setupCode = setup_code
        self.updateCode = update_code

    @staticmethod
    def parse(penstr):
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
        return Pen(display, interval, mode, colour, in_legend, setup_code, update_code)

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
        source = fp.readline().strip()
        precision = int(fp.readline())
        res1 = fp.readline()
        font_size = int(fp.readline())
        return Monitor(left, top, right, bottom, display, source, precision,
                       font_size)

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
        return Output(left, top, right, bottom, font_size)

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

class BahaviorSpaceXMLError(Exception):
    """
    Exception class for when there is unexpected content in the BehaviorSpace
    section of a NetLogo file.
    """
    def __init__(self, file, expected, found):
        self.file = file
        self.expected = exected
        self.found = found

    def __str__(self):
        return "BehaviorSpace XML format error in file %s: expected \"%s\", found \"%s\""%(self.file, self.expected, self.found)

class SteppedValue:
    """
    A class containing data from a stepped value parameter exploration in a
    BehaviorSpace
    """
    def __init__(self, variable, first, step, last):
        self.variable = variable
        self.first = first
        self.step = step
        self.last = last

    @staticmethod
    def fromXML(xml, file_name):
        if xml.tag != "steppedValueSet":
            raise BehaviorSpaceXMLError(file_name, "steppedValueSet", xml.tag)
        return SteppedValue(xml.get("variable"), float(xml.get("first")),
                            float(xml.get("step")), float(xml.get("last")))

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

class Experiment:
    """
    Class containing data from a single BehaviorSpace experiment
    """
    def __init__(self, name, setup, go, final, time_limit, exit_condition,
                 metrics, stepped_values = [], enumerated_values = [],
                 repetitions = 1, sequential_run_order = True,
                 run_metrics_every_step = True):
        self.name = name
        self.setup = setup
        self.go = go
        self.final = final
        self.timeLimit = time_limit
        self.exitCondition = exit_condition
        self.metrics = metrics
        self.steppedValueSet = stepped_values
        self.enumeratedValueSet = enumerated_values
        self.repetitions = repetitions
        self.sequentialRunOrder = sequential_run_order
        self.runMetricsEveryStep = run_metrics_every_step

    @staticmethod
    def fromXMLString(str, file_name):
        """
        Parse a full <experiments>...</experiments> XML string into an
        array of Experiments, which is returned
        """
        experiments = []
        if str == None or str.strip() == "":
            return []
        xml = xml.XML(str)
        if xml.tag != "experiments":
            raise BehaviorSpaceXMLError(file_name, "experiments", xml.tag)
        for exp in xml:
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
    def fromWidgets(widgets, name, stop):
        """
        Create an Experiment object from the parameter and output widgets on
        the GUI. Current parameter settings on the GUI will be used as the
        parameter values, and outputs used as metrics.
        """
        setup = ""
        go = ""
        outputs = []
        params = []

        for w in widgets:
            if isinstance(w, Button):
                if(w.display == "setup" or w.code == "setup"):
                    setup = w.code
                elif(w.display == "go" or w.code == "go"):
                    go = w.code
            elif isinstance(w, Output) and not isinstance(w, OutputArea):
                outputs.append(w)
            elif isinstance(w, Parameter):
                params.append(w)

        expt = None
        if isinstance(stop, int):
            expt = Experiment(name, setup, go, "", stop, None, [])
        else:
            expt = Experiment(name, setup, go, "", None, str(stop), [])
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
                if p.datatypeStr() == 'string' and not p.settingStr().startswith('"') and not p.settingStr().startsWith('&quot;'):
                    valuearr.append('"' + p.settingStr() + '"')
                else:
                    valuearr.append(p.settingStr())
                new_enum_set.append(EnumeratedValue(p.variable(), valuearr))
            else:
                new_enum_set.append(EnumeratedValue(p, param[p]))
        return Experiment(self.name, self.setup, self.go, self.final, self.timeLimit,
                          self.exitCondition, self.metrics, [], new_enum_set,
                          self.repetitions, self.sequentialRunOrder,
                          self.runMetricsEveryStep)

    def withSamples(self, samples):
        """
        Create an experiment from this one, changing the parameter settings to
        be set randomly from the array of samples passed as argument
        """
        param = {}
        for s in samples:
            name = s.param.variable()
            value = s.sample()
            param[name] = value
        return self.withParameterSettings(param)

    def withNSamples(self, samples, n, final_save = False):
        """
        Create an array of experiments from this one, changing the parameter
        settings such that each is set randomly from the array of samples
        passed as argument
        """
        expts = []
        for i in range(0, n):
            new_name = "%s-%0*d" % (self.name, (1 + int(math.log10(n))), i)
            expt = self.withSamples(samples)
            expt.rename(new_name)
            if final_save:
                expt.finallySaveParamMetricsExpt()
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
    def writeExperiments(file_name, expts):
        """
        Save an array of experiments as an XML file
        """
        try:
            fp = io.open(file_name, "w")
        except IOError as e:
            sys.stderr.write("Error creating file %s: %s\n"%(file_name, e.strerror))
            return False

        Experiment.writeExperimentHeader(fp)

        for expt in expts:
            expt.writeExperimentDetails(fp)

        Experiment.writeExperimentFooter(fp)

        fp.close()
        return True

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
                     %(v.variable, v.first, v.step, v.last))

        for v in self.enumeratedValueSet:
            fp.write(u"    <enumeratedValueSet variable=\"%s\">\n" % v.variable)
            for w in v.values:
                fp.write(u"      <value value=\"%s\"/>\n" % str(w).replace('"', '&quot;'))
            fp.write(u"    </enumeratedValueSet>\n")

        fp.write(u"  </experiment>\n")

    def escape(self, str):
        """
        Escape ampersands, quotes and inequalities when writing XML data
        """
        return str.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

    def writeExperiment(self, file_name):
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
        self.sequentialRunOrder = bool(seq)

    def setRunMetricsEveryStep(self, run):
        self.runMetricsEveryStep = bool(run)

    def setSetup(self, setup):
        if isinstance(setup, Button):
            self.setup = setup.code
        else:
            self.setup = str(setup)

    def setGo(self, go):
        if isinstance(go, Button):
            self.go = go.code
        else:
            self.go = str(go)

    def setFinal(self, final):
        self.final = str(final)

    def finallySaveParamMetrics(self, file_name):
        paramStr = ""
        wordStr = ""
        for v in self.steppedValueSet:
            paramStr = paramStr + v.variable + ","
            wordStr = wordStr + v.variable + " \",\" "
        for v in self.enumeratedValueSet:
            paramStr = paramStr + v.variable + ","
            wordStr = wordStr + v.variable + " \",\" "
        for m in self.metrics:
            paramStr = paramStr + m.replace(",", ".") + ","
            wordStr = wordStr + "(" + m + ") \",\" "
        self.final = '''
            ifelse file-exists? "{file}" [
                file-open "{file}"
            ] [
                file-open "{file}"
                file-print "{param}"
            ]
            file-print (word {word})
            file-close
        '''.format(file = file_name, param = paramStr[:-1], word = wordStr[:-5])

    def finallySaveParamMetricsExpt(self):
        self.finallySaveParamMetrics(self.name + ".csv")

    def setTimeLimit(self, limit):
        self.timeLimit = float(limit)

    def setExitCondition(self, exitCond):
        self.exitCondition = str(exitCond)

    def clearMetrics(self):
        self.metrics = []

    def addMetric(self, metric):
        if isinstance(metric, Monitor):
            self.metrics.append(metric.source)
        elif isinstance(metric, Plot):
            for p in metric.getPens():
                self.addMetric(p)
        elif isinstance(metric, Pen):
            code = metric.updateCode
            if code.startswith('"plot '):
                code = code[6:-1]
            self.metrics.append(code)
        else:
            self.metrics = str(metric)

    def clearSteppedValueSet(self):
        self.steppedValueSet = []

    def addSteppedValue(self, variable, first, step, last):
        self.steppedValueSet.append(SteppedValue(str(variable), float(first), float(step), float(last)))

    def clearEnumeratedValueSet(self):
        self.enumeratedValueSet = []

    def addEnumeratedValue(self, variable, values):
        self.enumeratedValueSet.append(EnumeratedValue(str(variable), values))


class NetlogoModel:
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
        section = ""
        for line in fp:
            if line[0:-1] == "@#$#@#$#@":
                break
            section = section + line
        return section

    @staticmethod
    def read(file_name):
        try:
            fp = io.open(file_name)
        except IOError as e:
            sys.stderr.write("Error opening file %s: %s\n"%(file_name, e.strerror))
            return False

        code = NetlogoModel.readSection(fp)

        widgets = Widget.read(fp)

        info = NetlogoModel.readSection(fp)

        shapes = NetlogoModel.readSection(fp)

        version = NetlogoModel.readSection(fp)
        version = version[0:-1]

        preview = NetlogoModel.readSection(fp)

        sd = NetlogoModel.readSection(fp)

        behav = Experiment.fromXMLString(NetlogoModel.readSection(fp), file_name)

        hubnet = NetlogoModel.readSection(fp)

        link_shapes = NetlogoModel.readSection(fp)

        settings = NetlogoModel.readSection(fp)

        deltatick = NetlogoModel.readSection(fp)

        return NetlogoModel(code, widgets, info, shapes, version, preview,
                            sd, behav, hubnet, link_shapes, settings, deltatick)

    def getParameters(self):
        if len(self.params) == 0:
            for w in self.widgets:
                if(isinstance(w, Parameter)):
                    self.params[w.variable()] = w
        return self.params

    def getExperiments(self):
        if len(self.expts) == 0 and len(self.behav) != 0:
            for b in self.behav:
                self.expts[b.name] = b
        return self.expts

    def writeParameters(self, file_name):
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
                else:
                    fp.write(u",%s,%s\n"%(param[key].settingStr(), param[key].settingStr()))
            elif param[key].datatypeStr() == 'boolean':
                fp.write(u",true,false\n")
            else:
                fp.write(u",NA,NA\n")

        fp.close()

    def printExperiments(self):
        if len(self.behav):
            print "There are no experiments"
        else:
            print "Experiments:"
            for expt in self.behav:
                print "\t" + expt.name

class Sample:
    def __init__(self, param, datatype, setting, minimum, maximum):
        self.param = param
        self.setting = setting
        self.datatype = datatype
        self.minimum = minimum
        self.maximum = maximum

    @staticmethod
    def read(file_name, params):
        try:
            fp = io.open(file_name)
        except IOError as e:
            sys.stderr.write("Error opening file %s: %s\n"%(file_name, e.strerror))
            return False

        header = fp.readline().strip()

        samples = []
        for line in fp:
            line = line.strip()
            words = line.split(",")
            if words[0] in params:
                param = params[words[0]]
                samples.append(Sample(param, words[1], words[2], words[3], words[4]))
            else:
                sys.stderr.write("Warning: parameter %s ignored\n" % words[0])

        fp.close()
        return samples

    def sample(self):
        if self.minimum == "NA" or self.maximum == "NA":
            return self.setting
        elif self.minimum == self.maximum:
            if isinstance(self.param, Chooser):
                return self.param.choices[int(self.maximum)]
            else:
                return self.minimum
        else:
            if self.datatype == "integer":
                rint = rnd.randint(int(self.minimum), int(self.maximum))
                if isinstance(self.param, Chooser):
                    return self.param.choices[rint]
                else:
                    return rint
            elif self.datatype == "numeric":
                return rnd.uniform(float(self.minimum), float(self.maximum))
            elif self.datatype == "boolean":
                return (rnd.random() < 0.5)
            else:
                return self.setting

    def setSample(self):
        self.param.setValue(self.sample())

if __name__ == "__main__":
    nlogo = sys.argv[1]
    model = NetlogoModel.read(nlogo)
    if(model == False):
        sys.exit(1)
    print "Read " + nlogo
    cmd = sys.argv[2]
    if cmd == 'param':
        model.writeParameters(sys.argv[3])
    elif cmd == 'expts':
        model.printExperiments()
    elif cmd == 'monte' or cmd == 'montq':
        samples = Sample.read(sys.argv[3], model.getParameters())
        expt = Experiment.fromWidgets(model.widgets, "x", int(sys.argv[4]))
        expts = expt.withNSamples(samples, int(sys.argv[5]), True)
        Experiment.writeExperiments(sys.argv[6], expts)
        if cmd == 'montq':
            try:
                fp = io.open(sys.argv[7], "w")
            except IOError as e:
                sys.stderr.write("Error creating file %s: %s\n"%(sys.argv[7], e.strerror))
            fp.write(u'''#!/bin/sh
#$ -cwd
#$ -t 1-{nsamp}
#$ -pe smp {threads}
printf -v JOB_ID "%0{size}d" $(expr $SGE_TASK_ID - 1)
export JAVA_HOME="{java_home}"
wd=`pwd`
cd "{nlogo_home}"
xml="$wd/{xml}"
xpt="x-$JOB_ID"
out="$wd/x-$JOB_ID.out"
csv="$wd/x-$JOB_ID-table.csv"
"{nlogo_invoke}" --model "$wd/{model}" --setup-file "$xml" --experiment "$xpt" --threads {threads} --table "$csv" > "$out" 2>&1
            '''.format(nsamp = int(sys.argv[5]),
                        size = (1 + int(math.log10(float(sys.argv[5])))), threads = 2,
                        java_home = os.getenv('JAVA_HOME', '/usr/bin/java'),
                        nlogo_home = os.getenv('NETLOGO_HOME', '/Applications/NetLogo 6.0.4'),
                        nlogo_invoke = os.getenv('NETLOGO_INVOKE', '/Applications/NetLogo 6.0.4/netlogo-headless.sh'),
                        xml = sys.argv[6], model = nlogo))
            fp.close()
            os.chmod(sys.argv[7], 0775)
    else:
        sys.stderr.write("Command \"%s\" not recognized\n"%(cmd))
    sys.exit(0)

#!/usr/local/bin/python3
"""
nlogui.py

A GUI for nlogo.py -- it has sort of got to a point where this is needed
because there are too many options for nlogo.py. A terminal-based Q&A
should also be available in case your context only provides that as an option.
"""
# Copyright (C) 2022  The James Hutton Institute
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
import nlogo as nl
from tkinter import *
from tkinter import filedialog
from tkinter import font
from tkinter import ttk
import os.path


################################################################################
# GUI
#
#    ####  #   #  ###
#   #      #   #   #
#   # ###  #   #   #
#   #   #  #   #   #
#    ###    ###   ###
#
################################################################################

class GUI:
    """
    GUI class. The basic layout is that there will be:

      + A toolbar at the top with buttons
      + Another row indicating the current working NetLogo model (once open)
      + Underneath those two, spanning the remaining rows, on the left, is a
        treeview with experiments, parameters and metrics in
      + Spanning the top, to the right of the treeview, is the nlogo.py command
        that is being built up, with buttons to run it and copy it
      + Underneath the nlogo.py command is split into three parts, the bottom
        containing any output from running any commands, the top containing a
        "working area" frame (with buttons/user input), and the middle containing
        information.
      + Underneath all that is a small row with quick messages in

    So, there are two columns and seven rows
    """

    no_file_chosen_text = "(Open a NetLogo file)"
    default_cmd = "nlogo.py"

    def __init__(self):
        self.root = Tk()
        self.root.title = 'nloGUI'
        self.platform = self.root.tk.call('tk', 'windowingsystem')

        self.mainframe = ttk.Frame(self.root, padding = "3 3 12 12")
        self.mainframe.grid(column = 0, row = 0, sticky = "nsew")
        self.root.columnconfigure(0, weight = 1)
        self.root.rowconfigure(0, weight = 1)
        self.menu(self.root)

        self.toolframe = ttk.Frame(self.mainframe)
        self.modelframe = ttk.Frame(self.mainframe)
        self.cmdframe = ttk.Frame(self.mainframe)
        treewidget = self.tree(self.mainframe)
        self.workframe = ttk.Frame(self.mainframe)
        self.infoframe = ttk.Frame(self.mainframe)
        self.outframe = ttk.Frame(self.mainframe)
        self.msglabel = ttk.Label(self.mainframe, text = "")

        self.toolframe.grid(column = 0, row = 0, columnspan = 2, sticky = "nsew")
        self.modelframe.grid(column = 0, row = 1, columnspan = 2, sticky = "nsew")
        self.cmdframe.grid(column = 1, row = 2, sticky = "nsew")
        treewidget.grid(column = 0, row = 2, rowspan = 4, sticky = "nsew")
        self.workframe.grid(column = 1, row = 3, sticky = "nsew")
        self.infoframe.grid(column = 1, row = 4, sticky = "nsew")
        self.outframe.grid(column = 1, row = 5, sticky = "nsew")
        self.msglabel.grid(column = 0, row = 6, columnspan = 2, sticky = "nsw")

        self.toolbar(self.toolframe)
        self.model(self.modelframe)
        self.command(self.cmdframe)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx = 5, pady = 5)

        self.key_status = { 'Meta_L': False, 'Control_L': False,
            'Meta_R': False, 'Control_R': False }

        for special in self.key_status.keys():
            self.root.bind_all('<' + 'KeyPress-' + special + '>', self.keyDown)
            self.root.bind_all('<' + 'KeyRelease-' + special + '>', self.keyUp)

        self.root.bind_all('<KeyPress-o>', self.keyOpenModel)
        self.root.bind_all('<KeyPress-q>', self.keyQuit)
        self.root.bind_all('<KeyPress-k>', self.keyCopyCommand)

        self.root.mainloop()

    def keyDown(self, event):
        self.key_status[event.keysym] = True
        if self.platform == 'aqua':
            if event.keysym == 'Meta_L' or event.keysym == 'Meta_R':
                self.msglabel['text'] = 'Cmd-'
        else:
            if event.keysym == 'Control_L' or event.keysym == 'Control_R':
                self.msglabel['text'] = 'Ctrl-'

    def keyUp(self, event):
        self.key_status[event.keysym] = False
        if self.msglabel['text'] == "Cmd-" or self.msglabel['text'] == 'Ctrl-':
            self.msglabel['text'] = ""

    def ctrl(self, key):
        if self.platform == 'aqua':
            return 'Command-' + key
        else:
            return 'Ctrl-' + key

    def menu(self, root):
        root.option_add('*tearOff', False)
        window = root
        self.menubar = Menu(window)
        self.filemenu = Menu(self.menubar, name = 'apple') if self.platform == 'aqua' else Menu(self.menubar)
        self.editmenu = Menu(self.menubar)
        if self.platform == 'aqua':
            self.menubar.add_cascade(menu = self.filemenu, label = 'nloGUI')
        else:
            self.menubar.add_cascade(menu = self.filemenu, label = 'File')

        self.menubar.add_cascade(menu = self.editmenu, label = 'Edit')
        self.filemenu.add_command(label = 'Open...', command = self.openModel)
        self.filemenu.entryconfigure('Open...', accelerator = self.ctrl('O'))

        self.filemenu.add_command(label = 'Quit', command = root.quit)
        self.filemenu.entryconfigure('Quit', accelerator = self.ctrl('Q'))

        self.editmenu.add_command(label = 'Copy Command', command = self.copyCommand)
        self.editmenu.entryconfigure('Copy Command', accelerator = self.ctrl('K'))

        window['menu'] = self.menubar

    def toolbar(self, frame):
        self.splitbutton = ttk.Button(frame, text = "Split", command = self.splitExperiment)
        self.splitbutton.state(['disabled'])
        self.splitbutton.grid(column = 1, row = 0)

        self.montebutton = ttk.Button(frame, text = "Monte", command = self.monteExperiment)
        self.montebutton.state(['disabled'])
        self.montebutton.grid(column = 2, row = 0)

        self.build_script = BooleanVar(value = True)
        self.scriptcheck = ttk.Checkbutton(frame, text = "Create Submission Script",
            variable = self.build_script, onvalue = True, offvalue = False)
        self.scriptcheck.grid(column = 3, row = 0)

        return frame

    def model(self, frame):
        label = ttk.Label(frame, text = "Model:")
        label.grid(column = 0, row = 0, sticky = "w")

        self.filelabel = ttk.Label(frame, text = GUI.no_file_chosen_text)
        self.filelabel.grid(column = 1, row = 0)

        return self.filelabel

    def command(self, frame):
        label = ttk.Label(frame, text = "Command:")
        label.grid(column = 0, row = 0, sticky = "w")

        self.cmdlabel = ttk.Label(frame, text = GUI.default_cmd, font = font.nametofont("TkFixedFont"))
        self.cmdlabel.grid(column = 1, row = 0)

        self.runbutton = ttk.Button(frame, text = "Run", command = self.runCommand)
        self.runbutton.grid(column = 2, row = 0, sticky = "e")

        return frame

    def newtree(self, tree):
        self.exptnode = tree.insert('', 'end', 'expts', text = 'Experiments')
        self.paramnode = tree.insert('', 'end', 'params', text = 'Parameters')
        self.monitornode = tree.insert('', 'end', 'monitors', text = 'Monitors')
        self.plotnode = tree.insert('', 'end', 'plots', text = 'Plots')

    def tree(self, frame):
        self.tree = ttk.Treeview(frame, selectmode = "browse")
        self.newtree(self.tree)
        return self.tree

    def retree(self, nlogo):
        self.tree.delete('expts')
        self.tree.delete('params')
        self.tree.delete('monitors')
        self.tree.delete('plots')
        self.newtree(self.tree)
        self.treedict = {}
        self.expts = nlogo.getExperiments()
        for name in sorted(self.expts.keys()):
            expt = self.tree.insert('expts', 'end', text = name, tags = ('tree-expt'))
            self.treedict[expt] = ('__expt__', name)
            xstep = self.tree.insert(expt, 'end', text = 'Stepped Parameters')
            for param in self.expts[name].getSteppedParameters():
                id = self.tree.insert(xstep, 'end', text = param.variable, tags = ('tree-expt-step'))
                self.treedict[id] = ('__step__', name, param.variable)
            xenum = self.tree.insert(expt, 'end', text = 'Enumerated Parameters')
            for param in self.expts[name].getEnumeratedParameters():
                id = self.tree.insert(xenum, 'end', text = param.variable, tags = ('tree-expt-enum'))
                self.treedict[id] = ('__enum__', name, param.variable)
            xmetx = self.tree.insert(expt, 'end', text = 'Metrics')
            for metc in self.expts[name].getMetrics():
                id = self.tree.insert(xmetx, 'end', text = metc, tags = ('tree-expt-metx'))
                self.treedict[id] = ('__metric__', name, param.variable)

        self.params = nlogo.getParameters()
        for name in sorted(self.params.keys()):
            id = self.tree.insert('params', 'end', text = name, tags = ('tree-param'))
            self.treedict[id] = ('__parameter__', name)

        self.monitors = nlogo.getMonitors()
        for name in sorted(self.monitors.keys()):
            id = self.tree.insert('monitors', 'end', text = name, tags = ('tree-mon'))
            self.treedict[id] = ('__monitor__', name)

        self.plots = nlogo.getPlots()
        for name in sorted(self.plots.keys()):
            plot = self.tree.insert('plots', 'end', text = name, tags = ('tree-plot'))
            self.treedict[plot] = ('__plot__', name)
            for pen in sorted(self.plots[name].getPenDict().keys()):
                id = self.tree.insert(plot, 'end', text = pen, tags = ('tree-plot-pen'))
                self.treedict[id] = ('__plot_pen__', name, pen)

        self.tree.tag_bind('tree-expt', '<1>', self.treeClickExpt)
        self.tree.tag_bind('tree-expt-step', '<1>', self.treeClickExptStep)
        self.tree.tag_bind('tree-expt-enum', '<1>', self.treeClickExptEnum)
        self.tree.tag_bind('tree-expt-metx', '<1>', self.treeClickExptMetric)
        self.tree.tag_bind('tree-param', '<1>', self.treeClickParameter)
        self.tree.tag_bind('tree-mon', '<1>', self.treeClickMonitor)
        self.tree.tag_bind('tree-plot', '<1>', self.treeClickPlot)
        self.tree.tag_bind('tree-plot-pen', '<1>', self.treeClickPlotPen)

    def treeClickExpt(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, expt) = self.treedict[id]
            print("You clicked on experiment {e}".format(e = expt))

    def treeClickExptStep(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, expt, par) = self.treedict[id]
            print("You clicked on stepped parameter {p} in experiment {e}".format(e = expt, p = par))

    def treeClickExptEnum(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, expt, par) = self.treedict[id]
            print("You clicked on enumerated parameter {p} in experiment {e}".format(e = expt, p = par))

    def treeClickExptMetric(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, expt, metc) = self.treedict[id]
            print("You clicked on metric {m} in experiment {e}".format(e = expt, m = metc))

    def treeClickParameter(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, param) = self.treedict[id]
            print("You clicked on parameter {p}".format(p = param))

    def treeClickMonitor(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, mon) = self.treedict[id]
            print("You clicked on monitor {m}".format(m = mon))

    def treeClickPlot(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, plot) = self.treedict[id]
            print("You clicked on plot {p}".format(p = plot))

    def treeClickPlotPen(self, event):
        id = self.tree.focus()
        if id in self.treedict:
            (x, plot, pen) = self.treedict[id]
            print("You clicked on pen {pp} in plot {p}".format(p = plot, pp = pen))

    def openModel(self):
        self.msglabel['text'] = "Getting filename..."
        filename = filedialog.askopenfilename(filetypes = [["NetLogo Models", ".nlogo", ""]],
            title = "Choose a NetLogo model")
        self.mainframe.focus_set()
        if filename != False and filename != "":
            self.filelabel['text'] = filename
            self.msglabel['text'] = "Opening " + os.path.basename(filename)
            self.opts = nl.Options(["nlogui.py", filename, "__GUI__"])
            self.nlogo = nl.NetlogoModel.read(self.opts)
            self.retree(self.nlogo)
            self.splitbutton.state(['!disabled'])
            self.montebutton.state(['!disabled'])
            self.msglabel['text'] = "Read " + os.path.basename(filename)
        else:
            self.msglabel['text'] = "File open cancelled"

    def copyCommand(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cmdlabel['text'])
        self.msglabel['text'] = "Command copied to clipboard"

    def runCommand(self):
        print("Running command \"{cmd}\"".format(cmd = self.cmdlabel['text']))

    def modifierDown(self):
        if self.platform == "aqua":
            return self.key_status['Meta_L'] or self.key_status['Meta_R']
        else:
            return self.key_status['Control_L'] or self.key_status['Control_R']

    def keyCopyCommand(self, event):
        if self.modifierDown():
            self.copyCommand()

    def keyRunCommand(self, event):
        if self.modifierDown():
            self.runCommand()

    def keyQuit(self, event):
        if self.modifierDown():
            self.root.quit()

    def keyOpenModel(self, event):
        if self.modifierDown():
            self.openModel()

    def monteExperiment(self):
        if self.build_script.get():
            print("You asked for a Monte Carlo experiment with script built")
        else:
            print("You asked for a Monte Carlo experiment without script")

    def splitExperiment(self):
        if self.build_script.get():
            print("You asked to split an experiment with script built")
        else:
            print("You asked to split an experiment without script")


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
    gui = GUI()

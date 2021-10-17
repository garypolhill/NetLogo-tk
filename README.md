# NetLogo-tk
Toolkit for NetLogo (various scripts)

This repository contains a series of scripts to help with analysing and processing output from NetLogo:

1. [`csv2sql.pl`](#csv2sqk.pl) -- generic script to convert CSV files to SQL
2. [`dotworld.pl`](#dotworld.pl) -- script to create a GraphViz compatible DOT file for drawing networks from the output of `export-world`
3. [`netlogo2R.pl`](#netlogo2R.pl) -- script to convert NetLogo CSV output to R-compatible CSV
4. [`nlogo.py`](#nlogo.py) -- Python (2.7) script to mess around with NetLogo models

## csv2sql.pl
Perl script converting generic CSV files to SQL. Usage:

`./csv2sql.pl [-db <database name>] [-tablespace <tablespace name>] [-netlogo-table] [-merge <table name>] <SQL file> <CSV files...>`

Creates the SQL file named in the argument (which must have a .sql suffix) from the CSV files. By default, one table is created per CSV file. If you want to merge the CSV files, use the -merge option and specify a name for the merged table.

Options:

  `-db <database name>` Adds a `create database` command to the SQL output
  `-tablespace <tablespace name>` Adds a `create tablespace` command to the SQL output
  `-netlogo-table` Skips the first six lines of each CSV file. The CSV files are assumed to be table-style output from BehaviorSpace, and the first six lines contain metadata about the run, which are ignored (for now).
  `-merge <table name>` Creates one table, using fields from the header line of the first CSV file. All subsequent CSV files are expected to only have fields belonging to the set of fields in the first CSV file -- if this does not apply, an exception will be generated.

## dotworld.pl
Perl script creating a DOT graph for [graphviz](https://www.graphviz.org/) of a network of agents from the output of `export-world` in NetLogo. Usage:

`./dotworld.pl -nodata {-label <breed> <var>} <DOT file> <world file> <start node var>=<start node value> <link breeds...>`

Create a DOT graph of a network of agents generated from the `export-world` output in world file starting at a given agent or breed, and expanding the graph using the named link breeds. To start at a breed, use `breed=<breed>` (e.g. `breed=turtle`) for the `<start node var>=<start node value>` argument. To start at a specific agent (i.e. an ego-net), use `who=<number>` (e.g. `who=173`) for that argument.

Options:

  `-nodata` By default, each node will be displayed as a table containing values for each non-null attribute of the corresponding agent. To over-ride this, and show just the name of the agent, use this argument.
  `-label <breed> <var>` This option can appear more than once, and allows you to use a variable other than `who` as a label for each agent node.

## netlogo2R.pl
Create a single R-compatible CSV file from multiple NetLogo output files. Usage:

`./netlogo2R.pl [-sep <separator>] [-metadata] <R file> <NetLogo output files...>`

NetLogo's CSV output files are not immediately readable by R, and this script can collate several CSV files and format them such that they are. You can specify a non-standard separator using the `sep` option, and include run metadata on each line using the `-metadata` option.

## nlogo.py
Python script to mess around with NetLogo models.

Run from the command line, it can be used to:

* Extract all the parameters from the model's GUI tab into a CSV file (This can then be used in a subsequent call to create an experiment)

  `./nlogo.py <nlogo file> param <file to save parameters to>`

* Print a list of the experiments from the model's behaviour space

  `./nlogo.py <nlogo file> expt`

* Split all the runs in an experiment so they can be executed separately

  `./nlogo.py <nlogo file> split <experiment name> <experiment XML file>`

  The experiment XML file then contains one experiment for each unique
  parameter setting in the named experiment. If your experiment has several
  repetitions, then these have not been split up. 

* Split the runs in an experiment and prepare a Sun Grid Engine shell script
  to submit them to a cluster

  `./nlogo.py <nlogo file> splitq <experiment name> <experiment XML file>
                                <file to save SGE submission script to>`

  You can then submit the jobs with `qsub <SGE submission script>`


* Prepare a Monte Carlo sample of parameter space

  `./nlogo.py <nlogo file> monte <parameter file> <tick number to stop at>
                                <number of samples> <experiment XML file>`

  Note: if the number of samples is large, the XML library used by NetLogo
  to read in the experiment file can cause out-of-memory and garbage
  collection errors, or result in the model taking a long time to run. Use
  number of samples > 10000 with caution.

  Update: The script now splits large numbers of samples (>= 10000) into
  batches of 5000 runs each.

  The created experiment file automatically collects data from plot pens
  and monitors each step.

* Prepare a Monte Carlo sample of parameter space with a shell script to
  run all the options with Sun Grid Engine

  `./nlogo.py <nlogo file> montq <parameter file> <tick number to stop at>
                                <number of samples> <experiment XML file>
                                <file to save SGE submission script to>`

  You can then submit the jobs with `qsub <SGE submission script>`

A typical workflow would be to run this with `param` and then `montq`, before
`qsub`bing the submission script.

## shpinfo.jl

NetLogo's GIS package only supports [some projections](https://github.com/NetLogo/GIS-Extension)
for shape files, and it can be handy to see what's in a shapefile when processing
it. `shpinfo.jl` does this. You will require [Julia](https://julialang.org/), and
the [Shapefile](https://github.com/JuliaGeo/Shapefile.jl) and [DataFrames](https://dataframes.juliadata.org/stable/)
packages. (Start Julia from the command line, hit `]` to go to the `Pkg` prompt, and
then do `add Shapefile`, and then `add DataFrames`. Hit backspace to get out of the `Pkg`
prompt and `CTRL-D` to exit Julia. Note that you will need to add a link to /usr/local/bin/julia
from your Julia installation binary for this script to work. See the [platform-specific installation instructions](https://julialang.org/downloads/platform/))

To run it, just do `shpinfo.jl`. If you want a non-default number of values to be shown
for each feature, you can give the `--values <n>` option. If you don't want the script
to search recursively for all shapefiles under the current working directory, you can
specify one or more directories or shapefiles as command-line arguments. 

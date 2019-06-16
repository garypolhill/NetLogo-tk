# NetLogo-tk
Toolkit for NetLogo (various scripts)

## nlogo.py
Python script to mess around with NetLogo models.

Run from the command line, it can be used to:

* Extract all the parameters from the model's GUI tab into a CSV file (This can then be used in a subsequent call to create an experiment)

  `./nlogo.py <nlogo file> param <file to save parameters to>`

* Print a list of the experiments from the model's behaviour space

  `./nlogo.py <nlogo file> expt`

* Prepare a Monte Carlo sample of parameter space

  `./nlogo.py <nlogo file> monte <parameter file> <tick number to stop at> <number of samples> <experiment XML file>`

  Note: if the number of samples is large, the XML library used by NetLogo
  to read in the experiment file can cause out-of-memory and garbage
  collection errors, or result in the model taking a long time to run. Use
  number of samples > 10000 with caution.

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

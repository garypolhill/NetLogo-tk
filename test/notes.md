# What this Python program actually does

`nlogo.py` is a NetLogo file parser + experiment generator.

At a high level:

## Step 1: It reads the .nlogo file

It splits it into sections:

code
widgets (GUI)
BehaviorSpace XML
etc.

That happens here:

```
NetlogoModel.read(...)
```

## Step 2: It extracts experiments from BehaviorSpace

This bit:

`behav = Experiment.fromXMLString(...)`

So whatever is in your <experiment>...</experiment> block becomes an Experiment object.

## Step 3: It stores metrics exactly as strings

This is important:

```
elif elem.tag == "metric":
    metrics.append(elem.text)
```

So your metrics are literally just:

"mean [ag.env] of turtles"
"if ticks > 0 [plot ...]"

No validation. No sanity. Just vibes.

## Step 4: It optionally injects CSV-writing code

`self.finallySaveParamMetrics(...)`

builds:

```
file-print (word (metric1) "," (metric2) "," ...)
```

So every metric becomes:

(metric-expression)

## Step 5: NetLogo runs it

And this is where everything becomes fun.

#  Where BehaviorSpace gets metrics from

There are two completely different sources:

(A) BehaviorSpace <metric> tags

These:

<metric>mean [ag.env] of turtles</metric>

NetLogo evaluates these every tick (because you set runMetricsEveryStep="true").

(B) Your injected <final> block

This:

file-print (word (...) "," (...) "," ...)

This is custom logging, not BehaviorSpace metrics.

So:

BehaviorSpace metrics → stored internally by NetLogo
Your CSV → manually written at the end

Two parallel systems. 

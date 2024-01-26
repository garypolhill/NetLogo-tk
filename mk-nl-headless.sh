#!/bin/sh
HEADLESS="netlogo-headless.sh"
if [[ -e "$HEADLESS" ]]
then
  if [[ -x "$HEADLESS" ]]
  then
    chmod 644 $HEADLESS
    echo "Execute permission removed from Netlogo headless script $HEADLESS"
  fi

  xmx=`grep -v '^#' $HEADLESS | grep -c -- '-Xmx[0-9][0-9]*m'`
  pgc=`grep -v '^#' $HEADLESS | grep -c -- '-XX:+UseParallelGC'`
  ada=`grep -v '^#' $HEADLESS | grep -c -- '-XX:+AdaptiveGCThreading'`

  if [[ "$xmx" -ne 1 ]]
  then
    echo "Found $xmx uncommented lines in $HEADLESS with -Xmx match. Expecting 1."
    exit 1
  fi
  
  thr_max="ParallelGCThreads"

  if [[ "$pgc" -gt 1 ]]
  then
    echo "Found $pgc uncommented lines in $HEADLESS with -XX:+UseParallelGC match. Expecting 0 or 1."
    exit 1
  fi

  if [[ "$ada" -gt 0 ]]
  then
    echo "Found $ada uncommented lines in $HEADLESS with -XX:+AdaptiveGCThreading. Using ParallelGCMaxThreads."
    thr_max="ParallelGCMaxThreads"
  fi

  for gc in 3 7 11 15
  do
    for ram in 4096 6144 8192 16384 32768
    do
      gig=`expr $ram / 1024`

      file=`echo $HEADLESS | sed -e "s/\.sh$/-${gc}gc-${gig}Gi.sh/"`

      if [[ -e "$file" ]]
      then
        echo "Script for $gc threads and ${gig}G RAM $file already exists. Not over-writing it in case it is being used."
      else
	head -n 1 $HEADLESS > $file
	echo "prefs=/var/tmp/javaPrefs.\$\$" >> $file
	echo "mkdir \$prefs" >> $file
        tail -n +2 $HEADLESS | sed -e "s/-Xmx[0-9][0-9]*m/-Xmx${ram}m -XX:$thr_max=$gc -Djava.util.prefs.userRoot=\$prefs/" >> $file
	echo "rm -rf \$prefs" >> $file
        echo "Created script $file for $gc threads and ${gig}G RAM with preferences in /var/tmp/javaPrefs.\$\$"
        chmod 755 $file
      fi
    done
  done
else
  echo "Netlogo headless script $HEADLESS not found in current working directory `pwd`"
fi

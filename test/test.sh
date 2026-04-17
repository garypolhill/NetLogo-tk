#!/bin/sh
#SBATCH --begin=now
#SBATCH --cpus-per-task=4
#SBATCH --job-name=test
#SBATCH --time=1440
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --array=1-1
#SBATCH --mem-per-cpu=1024

TASK_NO=$SLURM_ARRAY_TASK_ID
if [[ "$#" -gt 0 ]]
then
  TASK_NO=$(expr $TASK_NO + $1)
fi
if [[ TASK_NO -gt 1 ]]
then
  exit
fi
tmphome=`mktemp -d "/var/tmp/{name}-HOME-$TASK_NO-XXXXXX"`
# No BATCH_ID this experiment
XML=test.xml
BDIR=.
EXPT_ID=x-1
RDIR="`pwd`/$BDIR"
test -d "$RDIR" || mkdir -p "$RDIR"
MDIR="`pwd`"
XDIR="`pwd`"

export JAVA_HOME="/mnt/apps/java/jdk-17.0.1"
cd "/mnt/apps/netlogo-6.4.0"
OUT="$RDIR/$EXPT_ID.out"
CSV="$RDIR/$EXPT_ID-table.csv"
HOME="$tmphome" $SHELL <<TMPHOMESH
srun  "/mnt/apps/netlogo-6.4.0/netlogo-headless-3gc-4Gi.sh" --model "$MDIR/test.nlogo" --setup-file "$XDIR/$XML" --experiment "$EXPT_ID" --threads 1 --table "$CSV" > "$OUT" 2>&1

TMPHOMESH
sleep 5 # Paranoia
/bin/rm -rf "$tmphome"

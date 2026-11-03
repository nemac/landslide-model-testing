#!/bin/bash
# Runs ON the machine (started by aws/start_run.sh). Runs the model for the slides given
# (fids; all slides when none), 16 at a time, with the watcher pushing the viewer data to
# GitHub as slides finish. When everything is done and pushed, the machine stops itself;
# bash aws/terminate.sh then deletes it.
#   nohup bash aws/remote_run.sh 21 22 ... > logs/remote_run.log 2>&1 &
cd "$(dirname "$0")/.."
export AVAFLOW_RUNDIR=$PWD/avaflow_runs    # runs stay in the repo folder (not in git)
export AVAFLOW_LEAN=1                      # keep only what the viewer needs, about 7 MB a run
export PATH=$HOME/.local/bin:$PATH
LOG=logs/avaflow_cloud.log
TOTAL=$(python3 -c "
import sys; from avaflow_run import load_slides
want=[int(a) for a in sys.argv[1:] if a.isdigit()]; print(len([f for f in load_slides() if not want or f in want]))" "$@")
echo "$(date '+%F %H:%M') run starting: $TOTAL slides, 16 at a time"
( python3 avaflow_run.py "$@" --workers 16 > $LOG 2>&1; echo "exit $?" >> $LOG ) &
bash aws/remote_watch.sh $LOG $TOTAL >> logs/watch.log 2>&1
echo "$(date '+%F %H:%M') run and final push done; stopping the machine"
sudo shutdown -h now

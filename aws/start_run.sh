#!/bin/bash
# Start the run on the machine, in the background, for the slides given (fids; all when
# none). Runs already on the machine are kept, so this can be started again after a stop.
#   bash aws/start_run.sh 21 22 23        a few slides
#   bash aws/start_run.sh $(seq 21 68)    the second source set
#   bash aws/start_run.sh                 every slide
# Follow it with: bash aws/status.sh
set -e
source "$(dirname "$0")/common.sh"
need_ip
if ssh $SSH_OPTS ubuntu@$IP "pgrep -f avaflow_run.py >/dev/null"; then
  echo "a run is already going on the machine; see bash aws/status.sh"; exit 1
fi
ssh $SSH_OPTS ubuntu@$IP "cd $REMOTE_DIR && mkdir -p logs && nohup bash aws/remote_run.sh $* > logs/remote_run.log 2>&1 &"
sleep 20
ssh $SSH_OPTS ubuntu@$IP "cd $REMOTE_DIR && cat logs/remote_run.log; head -3 logs/avaflow_cloud.log 2>/dev/null"
echo
echo "running. Progress: bash aws/status.sh"

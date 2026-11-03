#!/bin/bash
# How the run on the machine is going: runs finished, per slide, the latest push, cost so far.
#   bash aws/status.sh
set -e
source "$(dirname "$0")/common.sh"
need_ip
LAUNCHED=$(aws ec2 describe-instances --region "$REGION" --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].LaunchTime" --output text)
HOURS=$(python3 -c "from datetime import datetime,timezone; print(round((datetime.now(timezone.utc)-datetime.fromisoformat('$LAUNCHED'.replace('Z','+00:00'))).total_seconds()/3600,1))")
echo "machine: $INSTANCE_TYPE at $IP, up $HOURS h (about \$$(python3 -c "print(round($HOURS*0.714,2))") so far)"
ssh $SSH_OPTS ubuntu@$IP "cd $REMOTE_DIR 2>/dev/null || exit 0
echo \"run job: \$(pgrep -f 'avaflow_run.py' >/dev/null && echo going || echo not running)   r.avaflow now: \$(pgrep -f r.avaflow.main | wc -l)\"
[ -f logs/avaflow_cloud.log ] || { echo 'no run started yet'; exit 0; }
echo \"finished runs on the machine: \$(ls -d avaflow_runs/*/stopslope* 2>/dev/null | wc -l)\"
echo \"slides done this run: \$(grep -c ' done' logs/avaflow_cloud.log) of \$(head -1 logs/avaflow_cloud.log | cut -d' ' -f1)\"
echo 'runs finished per hour, last 6 h:'; for d in avaflow_runs/*/stopslope*; do stat -c %Y \$d; done 2>/dev/null | awk -v now=\$(date +%s) '{h=int((now-\$1)/3600); if(h<6) c[h]++} END{for(h=5;h>=0;h--) printf \"  %dh ago:%d\", h, c[h]; print \"\"}'
echo 'per slide (fid: done of 72):'; python3 -c \"
import os,glob; from avaflow_run import load_slides
s=load_slides(); print('  '+'  '.join(f'{f}:{len(glob.glob(os.path.join(\\\"avaflow_runs\\\", v[\\\"id\\\"], \\\"stopslope*\\\")))}' for f,v in sorted(s.items()) if f>20))\" 2>/dev/null
echo 'failures:'; grep -i 'failed\|Traceback' logs/avaflow_cloud.log | head -3 || true
echo 'latest push:'; tail -2 logs/watch.log 2>/dev/null || echo '  none yet'
df -h / | awk 'NR==2{print \"disk free: \" \$4}'"

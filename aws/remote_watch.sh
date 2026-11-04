#!/bin/bash
# Runs ON the machine (started by aws/remote_run.sh). Every PUSH_EVERY seconds, for the
# slides with runs finished since the last push: rebuild those slides' geopackages and
# figures, remake the tiles and index, commit viewer/public/data and push to master, which
# makes GitHub Pages rebuild the site. Once every slide is done the run makes its own final
# collect before writing "exit"; the watcher waits for that, draws the figures for anything
# not yet pushed and pushes one last time.
#   bash aws/remote_watch.sh logs/avaflow_cloud.log <number of slides>
cd "$(dirname "$0")/.."
LOG=$1; TOTAL=$2
PUSH_EVERY=${PUSH_EVERY:-7200}
STAMP=logs/last_push.stamp
# fids of the slides with a run folder newer than the last push
new_fids() {
  python3 - "$STAMP" <<'EOF'
import os, sys, glob
from avaflow_run import load_slides, RUNDIR
stamp = sys.argv[1]; since = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
out = []
for fid, s in sorted(load_slides().items()):
    if any(os.path.getmtime(d) > since for d in glob.glob(os.path.join(RUNDIR, s["id"], "stopslope*"))):
        out.append(str(fid))
print(" ".join(out))
EOF
}
push() {   # $1 = fids to collect and plot (empty: nothing new), $2 = label, $3 = "nocollect" to skip the collect
  [ -n "$1" ] || { echo "$(date '+%F %H:%M') nothing new to push"; return; }
  echo "$(date '+%F %H:%M') push $2 (slides $1)"
  : > logs/push_last.log
  touch $STAMP
  if [ "$3" != "nocollect" ]; then python3 avaflow_run.py --collect $1 >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (collect), see logs/push_last.log"; return; }; fi
  python3 avaflow_plots.py $1 >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (plots), see logs/push_last.log"; return; }
  python3 make_viewer_data.py >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (viewer data), see logs/push_last.log"; return; }
  git add viewer/public/data >> logs/push_last.log 2>&1
  if git diff --cached --quiet; then echo "nothing changed in the viewer data"; return; fi
  git commit -q -m "viewer data: $2

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" >> logs/push_last.log 2>&1
  # bring master in first. Copies sent up by copy_up.sh that have since been committed on
  # master would block the pull, so drop them (master's version replaces them); where master
  # and this machine both changed a data file, this machine's version wins.
  git fetch -q >> logs/push_last.log 2>&1
  for f in $(git ls-files --others --exclude-standard); do git cat-file -e "origin/master:$f" 2>/dev/null && rm -f "$f"; done
  git pull -q --rebase --autostash -X theirs >> logs/push_last.log 2>&1 && git push -q >> logs/push_last.log 2>&1 \
    && echo "pushed $(git log --oneline -1)" || echo "PUSH FAILED (git), see logs/push_last.log"
}
while true; do
  if grep -q '^exit' $LOG; then
    push "$(new_fids)" "final, $(grep -c ' done' $LOG) of $TOTAL slides done" nocollect; echo "run finished"; break
  fi
  # timed pushes stop once every slide is done: the run's own final collect is writing then
  if [ "$(grep -c ' done' $LOG)" -lt "$TOTAL" ] && { [ ! -f $STAMP ] || [ $(( $(date +%s) - $(stat -c %Y $STAMP) )) -ge $PUSH_EVERY ]; }; then
    push "$(new_fids)" "$(ls -d avaflow_runs/*/stopslope* 2>/dev/null | wc -l) runs, $(grep -c ' done' $LOG) of $TOTAL slides done"
  fi
  sleep 60
done

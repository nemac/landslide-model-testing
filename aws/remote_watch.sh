#!/bin/bash
# Runs ON the machine (started by aws/remote_run.sh). Watches the run log. After each
# slide finishes: that slide's geopackage and figures, then the tiles and index, then a
# commit of viewer/public/data pushed to master, which makes GitHub Pages rebuild the site.
# Once every slide is done the run makes its own final collect before writing "exit";
# the watcher waits for that, draws the figures for anything not yet pushed, and pushes
# one last time.
#   bash aws/remote_watch.sh logs/avaflow_cloud.log <number of slides>
cd "$(dirname "$0")/.."
LOG=$1; TOTAL=$2
push() {   # $1 = fids to collect and plot (empty: tiles only), $2 = label, $3 = "nocollect" to skip the collect
  echo "$(date '+%F %H:%M') push $2 (slides $1)"
  : > logs/push_last.log
  if [ -n "$1" ]; then
    if [ "$3" != "nocollect" ]; then python3 avaflow_run.py --collect $1 >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (collect), see logs/push_last.log"; return; }; fi
    python3 avaflow_plots.py $1 >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (plots), see logs/push_last.log"; return; }
  fi
  python3 make_viewer_data.py >> logs/push_last.log 2>&1 || { echo "PUSH FAILED (viewer data), see logs/push_last.log"; return; }
  git add viewer/public/data >> logs/push_last.log 2>&1
  if git diff --cached --quiet; then echo "nothing new to push"; return; fi
  git commit -q -m "viewer data: $2

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" >> logs/push_last.log 2>&1
  git pull -q --rebase --autostash >> logs/push_last.log 2>&1 && git push -q >> logs/push_last.log 2>&1 \
    && echo "pushed $(git log --oneline -1)" || echo "PUSH FAILED (git), see logs/push_last.log"
}
fids_between() { grep ' done' $LOG | sed -n "$(($1 + 1)),$2p" | sed -E 's/.*fid ([0-9]+).*/\1/' | paste -sd' ' -; }
last=0
while true; do
  n=$(grep -c ' done' $LOG)
  if grep -q '^exit' $LOG; then
    push "$(fids_between $last $n)" "all $n slides done" nocollect; echo "run finished"; break
  fi
  if [ "$n" -gt "$last" ] && [ "$n" -lt "$TOTAL" ]; then push "$(fids_between $last $n)" "$n of $TOTAL slides"; last=$n; fi
  sleep 60
done

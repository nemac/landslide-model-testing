#!/bin/bash
# Copy to the machine what git does not hold: the code as it is in this working tree,
# the input geopackages and cut terrain, the geopackages and summary already made, and
# the finished runs of the second source set from the external drive (only the files the
# scripts read back, about 7 MB a run) so the machine does not redo them.
#   bash aws/copy_up.sh
# Safe to run again; only changed files are sent. Next: bash aws/start_run.sh
set -e
source "$(dirname "$0")/common.sh"
need_ip
# rsync as an array, not a string: the include patterns must reach rsync unexpanded
RS=(rsync -az --stats -e "ssh $SSH_OPTS")
sent() { grep "files transferred"; }

echo "code"
"${RS[@]}" --exclude .git --exclude node_modules --exclude avaflow_runs --exclude avaflow_work --exclude grassdata \
  --exclude logs --exclude avaflow_download --exclude avaflow_build --exclude inputs --exclude outputs \
  --exclude viewer/dist --exclude .DS_Store "$REPO_DIR/" "ubuntu@$IP:$REMOTE_DIR/" | sent

echo "inputs (geopackages, soils, cut terrain)"
"${RS[@]}" "$REPO_DIR/inputs/" "ubuntu@$IP:$REMOTE_DIR/inputs/" | sent

echo "outputs (geopackages, summary, chart data; not the figures)"
"${RS[@]}" --include '*.gpkg' --include '*.csv' --include 'plots/' --include 'plots/charts.json' --exclude 'plots/*' --exclude '*' \
  "$REPO_DIR/outputs/" "ubuntu@$IP:$REMOTE_DIR/outputs/" | sent

if [ -d "$RUNS_ON_MAC" ]; then
  echo "finished runs of the second source set (uid-named folders on the external drive)"
  "${RS[@]}" --exclude 'LS-*' --include '*/' \
    --include '*_hflow_max.tif' --include '*_vflow_max.tif' --include '*_deposit.tif' --include '*_basechange.tif' \
    --include 'storm.json' --include 'storm_hydrograph.txt' --include '*_treach.asc' --include '*_volumes.txt' --exclude '*' \
    --prune-empty-dirs "$RUNS_ON_MAC/" "ubuntu@$IP:$REMOTE_DIR/avaflow_runs/" | sent
else
  echo "external drive not mounted; finished runs not copied"
fi
echo
echo "next: bash aws/start_run.sh"

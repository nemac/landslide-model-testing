# Running the landslide model on AWS (for Claude)

Read `aws/README.md` first; it explains the pieces. This file says how to drive them.

## Rules

- Everything runs from the repo folder on the user's laptop with `bash aws/<script>.sh`.
  Never run the `remote_*.sh` scripts by hand; `setup.sh` and `start_run.sh` send them.
- The machine costs money while it exists. Launch only when asked to run something, and
  remind the user to terminate when the run is done. Never launch a second machine; the
  scripts refuse if one is running.
- Never start a run while one is going (`start_run.sh` refuses). Never kill a run without
  asking; finished runs are kept, so a restart loses only the runs in progress.
- Do not edit the instance type, disk size or region without the user asking. They are in
  `aws/common.sh`.
- The AWS profile is `default` (the NEMAC general account), region us-east-1.
- While a cloud run is going, do not run `make_viewer_data.py` on the laptop or push
  `viewer/public/data`; the machine owns those files until it finishes.
- Report progress in plain words: runs finished, runs an hour, hours left, pushes made.

## The order

1. `bash aws/launch.sh` makes the machine and waits for SSH. About 2 minutes.
2. `bash aws/setup.sh` builds GRASS 8.4 from source, builds r.avaflow 4.0G, installs
   the Python packages with pip, builds tippecanoe, sets git up with the deploy key at
   `~/.ssh/landslide-deploy-key` and clones the repo. About 15 minutes. Its log goes to
   the terminal; when run from Claude, send it to `logs/aws_setup.log` and grep the
   `==` section headers and any `rror` lines.
3. `bash aws/copy_up.sh` sends the working tree, `inputs/`, the geopackages and summary
   in `outputs/`, and any finished runs from the external drive. Needs the drive mounted
   for the last part; it says so otherwise. The scan of the drive can take 10 minutes.
4. `bash aws/start_run.sh <fids>` starts the run in the background. Fids are the slide
   numbers from `avaflow_run.load_slides()`: 1 to 20 are the first source set, 21 up the
   second. No fids means every slide.
5. `bash aws/status.sh` any time. It reports the machine's uptime and cost, whether the
   run job is going, runs finished, runs per hour over the last 6 hours, per-slide counts,
   failures, and the latest push.
6. When status says the run finished and the last push worked: `bash aws/terminate.sh`.
   It asks for a `y`; run it in a terminal the user can answer, or tell the user to run it.

## Checking a push landed

The watcher commits `viewer/public/data` and pushes to master. Check with
`git log origin/master --oneline -3` after `git fetch`; commits are named
`viewer data: N of M slides`. GitHub Pages rebuilds from that push within a few minutes.

## When the laptop also has a run going

The laptop writes finished runs to the external drive, which `copy_up.sh` sends up. To hand
a set over to the cloud: run `copy_up.sh` once more so the latest finished runs are on the
machine, stop the laptop run and its watcher (`pkill -f avaflow_run.py; pkill -f push_on_done`),
then `start_run.sh` with the set's fids. The machine skips every run it already has.

## Known pitfalls

- macOS rsync is old; the scripts use only flags it has (`--stats`, not `--info`).
- Ubuntu 22.04's own GRASS is 7.8 and the ubuntugis repository does not install there,
  which is why `remote_setup.sh` builds 8.4.1 from source.
- The USDA soil service returns 503 now and then; `lookup_soils.py` retries. Run it on the
  laptop before copying up, so the machine never needs it.
- If SSH times out the user's public IP has changed: `bash aws/open_ssh.sh`.

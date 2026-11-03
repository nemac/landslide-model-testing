# Running the model on AWS

The whole run matrix (every slide, every stop slope, storm and release depth) takes days on
a laptop. These scripts run it on one on-demand EC2 machine instead, push the viewer data to
GitHub as each slide finishes so GitHub Pages updates on its own, and stop the machine when
everything is done.

## What gets made in AWS

| Thing | Setting | Why |
|---|---|---|
| Account and region | the `default` AWS CLI profile (NEMAC general), us-east-1 | same as the other NEMAC scripts |
| Machine | one on-demand c7i.4xlarge, 16 vCPU, 32 GB, Ubuntu 22.04 | r.avaflow uses one core per run, so 16 runs go at once |
| Disk | 60 GB gp3 | runs keep only the files the viewer needs, about 7 MB each |
| Network | the default VPC, subnet and security group; SSH opened from your current IP | nothing else is reachable |
| Key pair | `landslide-runner-key`, saved to `~/.ssh/landslide-runner-key.pem` | made on the first launch, kept |
| Tag | `Name=landslide-runner` | every script finds the machine by this tag |

Cost: about $0.71 an hour for the machine plus a few cents a day for the disk. Each run takes
10 to 12 minutes of one core, so a source set of 48 slides (3,456 runs) is roughly two days
and $35 to $45. The machine stops itself when done; `terminate.sh` deletes it so the disk
stops costing too.

## Before the first run

1. AWS CLI installed and `aws sts get-caller-identity --profile default` answering.
2. A deploy key for the GitHub repo, so the machine can push:
   - make it once: `ssh-keygen -t ed25519 -N "" -f ~/.ssh/landslide-deploy-key`
   - add the public half (`~/.ssh/landslide-deploy-key.pub`) at
     https://github.com/nemac/landslide-model-testing/settings/keys with **Allow write access** ticked.
3. GitHub Pages set to build from GitHub Actions (Settings, Pages, Source: GitHub Actions).
   The workflow in `.github/workflows/pages.yml` rebuilds the site on every push to master
   that touches `viewer/`.
4. The inputs that are not in git, in `inputs/`: the source area and release point
   geopackages, and `outputs/landslide_soils.csv` from `lookup_soils.py` (run it on the
   laptop first; it needs no GRASS).
5. Commit and push your code before starting, so the site built by Pages matches the data
   the machine pushes. While the machine is running, do not push changes to
   `viewer/public/data` from the laptop, or the two will fight over the tiles.

## The steps

Run everything from the repo folder on your laptop.

```
bash aws/launch.sh                  # make the machine, open SSH, wait for it (2 min)
bash aws/setup.sh                   # GRASS 8.4 from source, r.avaflow, python packages, tippecanoe, git, clone (15 min)
bash aws/copy_up.sh                 # code, inputs, outputs and any finished runs from the external drive
bash aws/start_run.sh $(seq 21 68)  # start the run for these slides (fids); no fids = every slide
bash aws/status.sh                  # progress, pace, latest push, cost so far; run any time
bash aws/terminate.sh               # when status shows the run finished: delete the machine
```

Other scripts:

- `bash aws/ssh.sh` opens a shell on the machine in the repo folder.
- `bash aws/open_ssh.sh` re-opens SSH when your public IP has changed and SSH times out.
- `aws/remote_setup.sh`, `aws/remote_run.sh` and `aws/remote_watch.sh` run on the machine;
  the scripts above send and start them. You never run them by hand.

## What happens on the machine

`remote_run.sh` starts `avaflow_run.py` for the slides asked for with 16 workers. Runs are
written to `avaflow_runs/` inside the repo folder (not in git) with only the files the
scripts read back: the peak depth, deposit and ground change grids, the arrival time grid,
the storm inflow file and the volume table.

`remote_watch.sh` pushes every two hours (PUSH_EVERY seconds). Each push rebuilds the
geopackages and figures of the slides with new runs, remakes the tiles and index with `make_viewer_data.py`, commits
`viewer/public/data` and pushes to master. GitHub Pages then rebuilds the site. When the
last slide is done the run makes its own final collect, the watcher pushes once more, and
the machine shuts down. Logs on the machine, in the repo folder:

- `logs/avaflow_cloud.log` the run itself, one block per run, `<uid> (fid N) done` per slide
- `logs/watch.log` each push and whether it worked
- `logs/push_last.log` the detail of the latest push

## If something goes wrong

- SSH times out: `bash aws/open_ssh.sh` (your IP changed), then try again.
- The run died (status shows "run job: not running" before every slide is done): look at
  the end of `logs/avaflow_cloud.log` with `bash aws/ssh.sh`, fix the cause, then
  `bash aws/start_run.sh` again with the same fids. Finished runs are kept and skipped.
- A push failed: `logs/push_last.log` says which step. A git failure usually means master
  moved under the machine; `bash aws/ssh.sh`, then `git pull --rebase --autostash && git push`.
- Start over: `bash aws/terminate.sh`, then from `launch.sh` again.

## Getting the full grids instead

By default the machine keeps about 7 MB a run. To keep everything r.avaflow writes (about
130 MB a run, for review in QGIS), remove `export AVAFLOW_LEAN=1` from `aws/remote_run.sh`,
raise `VOLUME_SIZE` in `aws/common.sh` to fit (130 MB times the number of runs), and copy
`avaflow_runs/` back with rsync before terminating.

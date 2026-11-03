#!/bin/bash
# Set the machine up: GRASS, r.avaflow, the Python packages, tippecanoe, git with the
# deploy key, and a clone of the repo. Runs aws/remote_setup.sh on the machine.
#   bash aws/setup.sh
# Next: bash aws/copy_up.sh
set -e
source "$(dirname "$0")/common.sh"
need_ip
[ -f "$DEPLOY_KEY" ] || { echo "deploy key missing: $DEPLOY_KEY"; exit 1; }
echo "deploy key"
ssh $SSH_OPTS ubuntu@$IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
scp $SSH_OPTS "$DEPLOY_KEY" ubuntu@$IP:~/.ssh/landslide-deploy-key
ssh $SSH_OPTS ubuntu@$IP "chmod 600 ~/.ssh/landslide-deploy-key"
echo "setting up (10 to 15 minutes)"
ssh $SSH_OPTS ubuntu@$IP 'bash -s' < "$(dirname "$0")/remote_setup.sh"
echo
echo "next: bash aws/copy_up.sh"

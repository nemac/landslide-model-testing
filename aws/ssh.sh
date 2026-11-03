#!/bin/bash
# Open a shell on the machine, in the repo folder.
#   bash aws/ssh.sh
set -e
source "$(dirname "$0")/common.sh"
need_ip
exec ssh $SSH_OPTS -t ubuntu@$IP "cd $REMOTE_DIR 2>/dev/null; exec bash -l"

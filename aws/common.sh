#!/bin/bash
# Settings shared by the aws/ scripts, and a helper that finds the running machine.
# Sourced, not run.
export AWS_PROFILE="${AWS_PROFILE:-default}"      # the NEMAC general account
REGION="us-east-1"
INSTANCE_TYPE="c7i.4xlarge"                       # 16 vCPU, 32 GB; about twice the Mac's pace
VOLUME_SIZE=60                                    # GB; runs keep only what the viewer needs (~7 MB each)
NAME="landslide-runner"                           # the Name tag; every script finds the machine by it
KEY_NAME="landslide-runner-key"
KEY_FILE="$HOME/.ssh/${KEY_NAME}.pem"
DEPLOY_KEY="$HOME/.ssh/landslide-deploy-key"      # lets the machine push to the GitHub repo
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR="/home/ubuntu/landslide-model-testing"
RUNS_ON_MAC="/Volumes/exertnaldrive1/landslides/grassoutput"
SSH_OPTS="-i $KEY_FILE -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30"

# the public IP of the running machine, or empty
find_ip() {
  aws ec2 describe-instances --region "$REGION" \
    --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].PublicIpAddress" --output text 2>/dev/null | grep -v None
}

# the IP, or stop with a message
need_ip() {
  IP=$(find_ip)
  [ -n "$IP" ] || { echo "no running $NAME machine; launch one with: bash aws/launch.sh"; exit 1; }
  [ -f "$KEY_FILE" ] || { echo "SSH key missing: $KEY_FILE"; exit 1; }
}

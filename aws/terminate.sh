#!/bin/bash
# Delete the machine so it stops costing money. Asks first. The key pair stays for next time.
#   bash aws/terminate.sh
set -e
source "$(dirname "$0")/common.sh"
ID=$(aws ec2 describe-instances --region "$REGION" --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=running,stopped,pending,stopping" \
  --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null | grep -v None || true)
[ -n "$ID" ] || { echo "no $NAME machine to delete"; exit 0; }
aws ec2 describe-instances --region "$REGION" --instance-ids "$ID" \
  --query "Reservations[0].Instances[0].[InstanceId,State.Name,InstanceType,PublicIpAddress,LaunchTime]" --output text
read -p "delete this machine? (y/N) " ok
[ "$ok" = "y" ] || { echo "kept"; exit 0; }
aws ec2 terminate-instances --region "$REGION" --instance-ids "$ID" >/dev/null
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$ID"
echo "deleted"

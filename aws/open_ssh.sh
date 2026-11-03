#!/bin/bash
# Allow SSH to the machine from this computer's current public IP. Safe to run again
# whenever the IP changes and SSH times out.
#   bash aws/open_ssh.sh
set -e
source "$(dirname "$0")/common.sh"
MY_IP=$(curl -s https://checkip.amazonaws.com)
[ -n "$MY_IP" ] || { echo "could not find this computer's public IP"; exit 1; }
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" --query "SecurityGroups[0].GroupId" --output text)
HAVE=$(aws ec2 describe-security-groups --region "$REGION" --group-ids "$SG_ID" \
  --query "SecurityGroups[0].IpPermissions[?ToPort==\`22\` && FromPort==\`22\`].IpRanges[].CidrIp" --output text | tr '\t' '\n' | grep -Fx "$MY_IP/32" || true)
if [ -n "$HAVE" ]; then
  echo "  SSH from $MY_IP already allowed"
else
  ERR=$(aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP/32" 2>&1 >/dev/null) \
    && echo "  SSH from $MY_IP allowed" || { echo "$ERR" | grep -q Duplicate && echo "  SSH from $MY_IP already allowed" || { echo "  could not add the SSH rule: $ERR"; exit 1; }; }
fi

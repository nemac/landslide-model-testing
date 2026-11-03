#!/bin/bash
# Launch the on-demand machine that runs the landslide model and pushes the viewer data.
#   bash aws/launch.sh
# Uses the default VPC, subnet and security group in us-east-1, opens SSH from this
# computer's public IP, makes the key pair on first use, then waits until SSH answers.
# Next: bash aws/setup.sh
set -e
source "$(dirname "$0")/common.sh"

if [ -n "$(find_ip)" ]; then
  echo "a $NAME machine is already running at $(find_ip)"; exit 0
fi

echo "default VPC, subnet and security group"
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
SUBNET_ID=$(aws ec2 describe-subnets --region "$REGION" --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" --query "Subnets[0].SubnetId" --output text)
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" --query "SecurityGroups[0].GroupId" --output text)
for v in VPC_ID SUBNET_ID SG_ID; do [ "${!v}" != "None" ] && [ -n "${!v}" ] || { echo "no default $v in $REGION"; exit 1; }; done
echo "  $VPC_ID $SUBNET_ID $SG_ID"

echo "SSH from this computer"
bash "$(dirname "$0")/open_ssh.sh"

echo "newest Ubuntu 22.04 image"
AMI_ID=$(aws ec2 describe-images --region "$REGION" --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)
echo "  $AMI_ID"

if ! aws ec2 describe-key-pairs --region "$REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
  echo "making key pair $KEY_NAME"
  aws ec2 create-key-pair --region "$REGION" --key-name "$KEY_NAME" --query KeyMaterial --output text > "$KEY_FILE"
  chmod 400 "$KEY_FILE"
elif [ ! -f "$KEY_FILE" ]; then
  echo "the key pair exists in AWS but $KEY_FILE is missing here; delete the key pair in AWS and run again"; exit 1
fi

echo "launching $INSTANCE_TYPE with ${VOLUME_SIZE} GB"
INSTANCE_ID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${VOLUME_SIZE},\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=project,Value=landslide-model-testing}]" \
                       "ResourceType=volume,Tags=[{Key=Name,Value=$NAME-volume},{Key=project,Value=landslide-model-testing}]" \
  --query "Instances[0].InstanceId" --output text)
echo "  $INSTANCE_ID"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
IP=$(find_ip)
echo "  running at $IP; waiting for SSH"
for i in $(seq 1 30); do
  ssh $SSH_OPTS -o ConnectTimeout=5 ubuntu@$IP true 2>/dev/null && break
  sleep 5
done
echo
echo "machine ready: $INSTANCE_TYPE at $IP"
echo "next: bash aws/setup.sh"

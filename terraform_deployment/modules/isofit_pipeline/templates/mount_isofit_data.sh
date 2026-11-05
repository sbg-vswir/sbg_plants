MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="==BOUNDARY=="

--==BOUNDARY==
Content-Type: text/x-shellscript; charset="us-ascii"

#!/bin/bash
# Mounts s3://${bucket}/${prefix} read-only at ${mount_path} with Mountpoint
# for Amazon S3, so ISOFIT jobs on this instance can read the large data
# (sRTMnet emulator, …) without it being baked into the image. The job
# definition bind-mounts ${mount_path} into the container read-only.
#
# Runs as user-data on the ECS-optimised AL2023 AMI, before the ECS agent
# starts, so no job lands on the instance before the mount exists. Reads are
# cached on local disk, so only the first job on an instance downloads.
set -euo pipefail

dnf install -y https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.rpm

mkdir -p ${mount_path} /var/cache/mount-s3

cat > /etc/systemd/system/isofit-data.service <<'UNIT'
[Unit]
Description=Mount s3://${bucket}/${prefix} at ${mount_path}
Wants=network-online.target
After=network-online.target
Before=docker.service ecs.service

[Service]
Type=forking
ExecStart=/usr/bin/mount-s3 ${bucket} ${mount_path} --prefix ${prefix} --region ${region} --read-only --allow-other --cache /var/cache/mount-s3 --max-cache-size ${cache_size_mib}
ExecStop=/usr/bin/fusermount -u ${mount_path}
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now isofit-data.service

# fail loudly in the instance log if the mount isn't there
mountpoint -q ${mount_path}
ls ${mount_path}

--==BOUNDARY==--

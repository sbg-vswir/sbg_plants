# ── Slim ISOFIT worker (side by side with the current one in main_batch.tf) ──
# Uses the slim image (isofit-PerPixel/Dockerfile.slim) — no sRTMnet emulator
# baked in. The large data lives in s3://<config bucket>/isofit-data/ and each
# instance mounts it read-only at /mnt/isofit-data with Mountpoint for S3
# (templates/mount_isofit_data.sh); the job definition bind-mounts it into the
# container. Containers are not privileged.
#
# Cut over later by pointing the pixel selection lambda's BATCH_JOB_QUEUE /
# BATCH_JOB_DEFINITION (and its batch:SubmitJob resources) at the *_slim
# resources below, then remove the old ones.

locals {
  isofit_data_mount = "/mnt/isofit-data"
}

# The instance (not the job) runs mount-s3, so the instance role reads the data
resource "aws_iam_role_policy" "batch_ec2_isofit_data" {
  role = aws_iam_role.batch_ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = var.config_bucket_arn
        Condition = { StringLike = { "s3:prefix" = ["${var.isofit_data_prefix}*"] } }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${var.config_bucket_arn}/${var.isofit_data_prefix}*"
      }
    ]
  })
}

resource "aws_launch_template" "batch_worker_slim" {
  name = "vswir-plants-batch-worker-slim"

  # slim image (~a few GB) + mount-s3 read cache
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 40
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  user_data = base64encode(templatefile("${path.module}/templates/mount_isofit_data.sh", {
    bucket         = var.config_bucket_name
    prefix         = var.isofit_data_prefix
    region         = var.region
    mount_path     = local.isofit_data_mount
    cache_size_mib = 15000
  }))

  tags = var.tags
}

resource "aws_batch_compute_environment" "worker_slim" {
  # name_prefix + create_before_destroy: changing compute_resources replaces
  # the environment, and the queue must move to the new one before the old
  # one can be deleted
  name_prefix  = "isofit-compute-slim-"
  type         = "MANAGED"
  service_role = aws_iam_role.batch_service_role.arn

  compute_resources {
    type           = "SPOT"
    bid_percentage = 60

    min_vcpus = 0
    max_vcpus = 40

    # Jobs are 8 vCPU / 12 GiB. c family is the main fit (.2xlarge = 8 vCPU /
    # 16 GiB, one job; .4xlarge = 16 vCPU / 32 GiB, two jobs). m .2xlarge is a
    # spot-capacity fallback (one job, memory left idle). 4-vCPU sizes can't
    # fit a job, so none are listed.
    instance_type = [
      "c6i.2xlarge",
      "c7i.2xlarge",
      "c6a.2xlarge",
      "c7a.2xlarge",
      "c6i.4xlarge",
      "c7i.4xlarge",
      "c6a.4xlarge",
      "c7a.4xlarge",
      "m6i.2xlarge",
      "m7i.2xlarge",
      "m6a.2xlarge",
      "m7a.2xlarge",
    ]

    subnets            = var.private_subnets
    security_group_ids = [aws_security_group.worker.id]

    # mount_isofit_data.sh uses dnf, so pin AL2023 rather than Batch's default AMI
    ec2_configuration {
      image_type = "ECS_AL2023"
    }

    launch_template {
      launch_template_id = aws_launch_template.batch_worker_slim.id
      version            = "$Latest"
    }

    instance_role       = aws_iam_instance_profile.batch_ec2.arn
    spot_iam_fleet_role = aws_iam_role.spot_fleet_role.arn
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_batch_job_queue" "worker_slim" {
  name     = "pixel-selection-queue-slim"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.worker_slim.arn
  }

  tags = var.tags
}

resource "aws_batch_job_definition" "worker_slim" {
  name           = "pixel-selection-worker-slim"
  type           = "container"
  propagate_tags = true

  container_properties = jsonencode({
    image   = var.ecr_image_slim
    command = ["bash", "-c", "aws s3 sync s3://vswir-plants-config/isofit-app/ /root/app/ --region us-west-2 && python3 /root/app/entrypoint.py"]

    resourceRequirements = [
      # measured on 10 SHIFT pixels: 8 vCPU = 271 s / 8.0 GiB peak,
      # 4 vCPU = 624 s / 6.6 GiB — 8 vCPU is faster and fewer vCPU-seconds
      { type = "VCPU", value = "8" },
      { type = "MEMORY", value = "12288" }
    ]

    executionRoleArn = aws_iam_role.batch_execution_role.arn
    jobRoleArn       = aws_iam_role.batch_job_role.arn

    linuxParameters = {
      sharedMemorySize = 5120
    }

    volumes = [
      { name = "isofit-data", host = { sourcePath = local.isofit_data_mount } }
    ]
    mountPoints = [
      { sourceVolume = "isofit-data", containerPath = local.isofit_data_mount, readOnly = true }
    ]

    environment = [
      { name = "DB_SECRET_ARN", value = aws_secretsmanager_secret.isofit_user.arn },
      { name = "DYNAMODB_TABLE", value = var.dynamodb_table_name },
      { name = "AWS_REGION", value = var.region },
      { name = "PYTHONPATH", value = "/root/app" },
      { name = "PYTHONUNBUFFERED", value = "1" },
      { name = "NCPU", value = "8" },
      # emulator .h5 on the mount; its <name>_aux.npz must sit next to it
      { name = "SRTMNET_FILE", value = "${local.isofit_data_mount}/${var.srtmnet_file}" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.batch.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "batch-slim"
      }
    }
  })

  retry_strategy {
    attempts = 2
  }

  timeout {
    attempt_duration_seconds = 1500
  }

  tags = var.tags
}

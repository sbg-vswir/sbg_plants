
data "aws_caller_identity" "current" {}

resource "aws_secretsmanager_secret" "isofit_user" {
  name        = "isofit_db_credentials"
  description = "Database credentials for isofit user Lambda"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "isofit_db_version" {
  secret_id = aws_secretsmanager_secret.isofit_user.id
  secret_string = jsonencode({
    username = var.isofit_user
    password = var.isofit_user_password
    host     = var.db_host_url
    dbname   = var.db_name
    port     = var.db_port
  })
}

# Lambda IAM
resource "aws_iam_role" "lambda_role" {
  name = "vswir-plants-pixel-selection-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_policy" "lambda_pixel_selection_policy" {
  name        = "vswir-plants-pixel-selection-policy"
  description = "Allow pixel selection Lambda to submit Batch jobs and write to DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["batch:SubmitJob"]
        Resource = [
          aws_batch_job_definition.worker.arn,
          "arn:aws:batch:${var.region}:${data.aws_caller_identity.current.account_id}:job-definition/${aws_batch_job_definition.worker.name}",
          aws_batch_job_queue.worker.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
        ]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.db_secret_arn
      },
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_pixel_selection_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_pixel_selection_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "pixel_selection" {
  function_name = "vswir-plants-pixel-selection"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.pixel_selection_ecr_image
  timeout       = 60

  vpc_config {
    subnet_ids         = var.private_subnets
    security_group_ids = [aws_security_group.worker.id]
  }

  environment {
    variables = {
      BATCH_JOB_QUEUE      = aws_batch_job_queue.worker.name
      BATCH_JOB_DEFINITION = aws_batch_job_definition.worker.name
      DYNAMODB_TABLE       = var.dynamodb_table_name
      DB_SECRET_ARN        = var.db_secret_arn
      BATCH_SIZE           = "20"
    }
  }

  tags = var.tags
}

# Lambda API Gateway Integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.pixel_selection.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pixel_selection.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

resource "aws_apigatewayv2_route" "run_algorithm" {
  api_id             = var.api_id
  route_key          = "POST /run_algorithm"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

# ── Pixel Output Promotion Lambda ────────────────────────────────────────────
# Promotes algorithm results from vswir_plants_staging output tables to
# vswir_plants production tables. Algorithm-agnostic — new data products
# are registered in the lambda's PRODUCT_REGISTRY, not in Terraform.

resource "aws_iam_role" "pixel_output_promotion_role" {
  name = "vswir-plants-pixel-output-promotion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_policy" "pixel_output_promotion_policy" {
  name        = "vswir-plants-pixel-output-promotion-policy"
  description = "Allow pixel output promotion Lambda to read DB credentials and update DynamoDB job records"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.isofit_user.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/parent_job_id-index",
        ]
      },
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "pixel_output_promotion_attach" {
  role       = aws_iam_role.pixel_output_promotion_role.name
  policy_arn = aws_iam_policy.pixel_output_promotion_policy.arn
}

resource "aws_iam_role_policy_attachment" "pixel_output_promotion_basic_execution" {
  role       = aws_iam_role.pixel_output_promotion_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "pixel_output_promotion_vpc_execution" {
  role       = aws_iam_role.pixel_output_promotion_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_lambda_function" "pixel_output_promotion" {
  function_name = "vswir-plants-pixel-output-promotion"
  role          = aws_iam_role.pixel_output_promotion_role.arn
  package_type  = "Image"
  image_uri     = var.pixel_output_promotion_ecr_image
  timeout       = 60

  vpc_config {
    subnet_ids         = var.private_subnets
    security_group_ids = [aws_security_group.worker.id]
  }

  environment {
    variables = {
      ISOFIT_DB_SECRET_ARN = aws_secretsmanager_secret.isofit_user.arn
      DYNAMODB_TABLE       = var.dynamodb_table_name
    }
  }

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "pixel_output_promotion" {
  name              = "/aws/lambda/vswir-plants-pixel-output-promotion"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_apigatewayv2_integration" "pixel_output_promotion" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.pixel_output_promotion.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_lambda_permission" "pixel_output_promotion_apigw" {
  statement_id  = "AllowAPIGatewayInvokePromotion"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pixel_output_promotion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

# POST /data_products/{product_key}/jobs/{job_id}/promote
resource "aws_apigatewayv2_route" "pixel_output_promote" {
  api_id             = var.api_id
  route_key          = "POST /data_products/{product_key}/jobs/{job_id}/promote"
  target             = "integrations/${aws_apigatewayv2_integration.pixel_output_promotion.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

# DELETE /data_products/{product_key}/jobs/{job_id} — delete staging rows without promoting
resource "aws_apigatewayv2_route" "pixel_output_delete" {
  api_id             = var.api_id
  route_key          = "DELETE /data_products/{product_key}/jobs/{job_id}"
  target             = "integrations/${aws_apigatewayv2_integration.pixel_output_promotion.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

# GET /data_products — returns registered algorithm registry to the frontend
resource "aws_apigatewayv2_route" "pixel_output_list_products" {
  api_id             = var.api_id
  route_key          = "GET /data_products"
  target             = "integrations/${aws_apigatewayv2_integration.pixel_output_promotion.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

# ── Batch Execution Role (same as ECS task execution role) ────────────────────
resource "aws_iam_role" "batch_execution_role" {
  name = "batchExecutionRolePixel"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "batch_execution" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Batch Job Role (what your container can do)
resource "aws_iam_role" "batch_job_role" {
  name = "pixel-selection-batch-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "batch_job_policy" {
  role = aws_iam_role.batch_job_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.isofit_user.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.config_bucket_arn,
          "${var.config_bucket_arn}/isofit-app/*"
        ]
      }
    ]
  })
}

# Batch Service Role
resource "aws_iam_role" "batch_service_role" {
  name = "pixel-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "batch.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# EC2 Instance Role — what the EC2 instance itself can do
resource "aws_iam_role" "batch_ec2_role" {
  name = "vswir-plants-batch-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "batch_ec2_container_service" {
  role       = aws_iam_role.batch_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "batch_ec2_ssm" {
  role       = aws_iam_role.batch_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "batch_ec2_cw_admin" {
  role       = aws_iam_role.batch_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentAdminPolicy"
}

resource "aws_iam_role_policy_attachment" "batch_ec2_cw_server" {
  role       = aws_iam_role.batch_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "batch_ec2_secrets" {
  role = aws_iam_role.batch_ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.isofit_user.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "batch_ec2" {
  name = "vswir-plants-batch-ec2-profile"
  role = aws_iam_role.batch_ec2_role.name
  tags = var.tags
}

# Spot Fleet Role — required for SPOT compute environments
resource "aws_iam_role" "spot_fleet_role" {
  name = "vswir-plants-spot-fleet-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "spotfleet.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  role       = aws_iam_role.spot_fleet_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

# Deliberately bare — no inline ingress/egress blocks. Every rule lives in its
# own aws_security_group_rule resource below. Mixing inline rule blocks with
# standalone aws_security_group_rule resources on the same SG causes them to
# fight over ownership of the rule set — the inline block treats itself as
# authoritative and tries to prune anything the standalone resources added,
# so every `terraform apply` shows a phantom diff that never converges. (This
# SG previously had both an inline CIDR-scoped 5432 egress rule *and* the
# standalone SG-scoped worker_to_db rule below — two different rules for the
# same port; the SG-scoped one is kept as the more precise of the two.)
resource "aws_security_group" "worker" {
  name   = "pixel-worker-sg"
  vpc_id = var.vpc_id

  tags = var.tags
}

resource "aws_security_group_rule" "worker_to_db" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.worker.id
  source_security_group_id = var.db_security_group_id
}

resource "aws_security_group_rule" "worker_to_aws_apis" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.worker.id
  description       = "aws apis (dynamodb, secrets manager, batch)"
}

# ── Launch template — ensures sufficient EBS for the isofit Docker image ──────
# The isofit image is ~13GB. Default ECS AMI root volume is 30GB which is
# too tight once OS + Docker overhead is included.
resource "aws_launch_template" "batch_worker" {
  name = "vswir-plants-batch-worker"

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 50
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tags = var.tags
}

# ── Batch Compute Environment ─────────────────────────────────────────────────
# EC2 Spot — uses stock ECS-optimised AL2023 AMI. The isofit Docker image
# is pulled on first job and cached on the instance for subsequent jobs.

resource "aws_batch_compute_environment" "worker" {
  name         = "isofit-compute"
  type         = "MANAGED"
  service_role = aws_iam_role.batch_service_role.arn

  compute_resources {
    type           = "SPOT"
    bid_percentage = 60

    min_vcpus = 0
    max_vcpus = 40

    instance_type = [
      "m5.xlarge",
      "m5.2xlarge",
      "m4.xlarge",
      "m4.2xlarge",
      "r5.xlarge",
    ]

    subnets            = var.private_subnets
    security_group_ids = [aws_security_group.worker.id]

    launch_template {
      launch_template_id = aws_launch_template.batch_worker.id
      version            = "$Latest"
    }

    instance_role       = aws_iam_instance_profile.batch_ec2.arn
    spot_iam_fleet_role = aws_iam_role.spot_fleet_role.arn
  }

  tags = var.tags
}

# ── FARGATE version (kept for reference) ──────────────────────────────────────
# resource "aws_batch_compute_environment" "worker_fargate" {
#   name         = "isofit-compute-fargate"
#   type         = "MANAGED"
#   service_role = aws_iam_role.batch_service_role.arn
#
#   compute_resources {
#     type      = "FARGATE_SPOT"
#     max_vcpus = 40
#
#     subnets            = var.private_subnets
#     security_group_ids = [aws_security_group.worker.id]
#   }
#
#   tags = var.tags
# }

# Batch Job Queue
resource "aws_batch_job_queue" "worker" {
  name     = "pixel-selection-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.worker.arn
  }

  tags = var.tags
}

# ── Batch Job Definition ──────────────────────────────────────────────────────

resource "aws_batch_job_definition" "worker" {
  name           = "pixel-selection-worker"
  type           = "container"
  propagate_tags = true

  container_properties = jsonencode({
    image   = var.ecr_image
    command = ["bash", "-c", "aws s3 sync s3://vswir-plants-config/isofit-app/ /root/app/ --region us-west-2 && python3 /root/app/entrypoint.py"]

    resourceRequirements = [
      { type = "VCPU", value = "4" },
      { type = "MEMORY", value = "14336" }
    ]

    executionRoleArn = aws_iam_role.batch_execution_role.arn
    jobRoleArn       = aws_iam_role.batch_job_role.arn

    linuxParameters = {
      sharedMemorySize = 5120
    }

    environment = [
      { name = "DB_SECRET_ARN", value = aws_secretsmanager_secret.isofit_user.arn },
      { name = "DYNAMODB_TABLE", value = var.dynamodb_table_name },
      { name = "AWS_REGION", value = var.region },
      { name = "PYTHONPATH", value = "/root/app" },
      { name = "PYTHONUNBUFFERED", value = "1" },
      { name = "NCPU", value = "4" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/batch/pixel-worker"
        awslogs-region        = var.region
        awslogs-stream-prefix = "batch"
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

# Cloudwatch log group
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/batch/pixel-worker"
  retention_in_days = 30
  tags              = var.tags
}
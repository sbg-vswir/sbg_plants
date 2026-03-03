
resource "aws_secretsmanager_secret" "isofit_user" {
  name        = "isofit_db_credentials"
  description = "Database credentials for isofit user Lambda"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "pygeoapi_db_version" {
  secret_id     = aws_secretsmanager_secret.pygeoapi_db.id
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
  name = "pixel-selection-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_batch" {
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["batch:SubmitJob"]
        Resource = [
          aws_batch_job_definition.worker.arn,
          aws_batch_job_queue.worker.arn
        ]
      },
      {
        # write initial submitted record to dynamo
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = var.dynamodb_table_arn
      },
      {
        # read pixel ids from postgres via secrets manager
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.db_secret_arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:*"]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "pixel_selection" {
  function_name = "pixel-selection"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"

  filename         = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")

  environment {
    variables = {
      BATCH_JOB_QUEUE      = aws_batch_job_queue.worker.name
      BATCH_JOB_DEFINITION = aws_batch_job_definition.worker.name
      DYNAMODB_TABLE       = var.dynamodb_table_name
      DB_SECRET_ARN        = var.db_secret_arn
      BATCH_SIZE           = "20"
    }
  }
}

# Lambda API Gateway Integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = var.api_id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.pixel_selection.invoke_arn
}

resource "aws_apigatewayv2_route" "pixel_selection" {
  api_id    = var.api_id
  route_key = "POST /run_isofit"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Batch Execution Role (same as ECS task execution role)
resource "aws_iam_role" "batch_execution_role" {
  name = "batchExecutionRolePixel"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
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
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
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
        # read db credentials from secrets manager
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.db_secret_arn
      },
      {
        # write job status and attempt history to dynamo
        Effect   = "Allow"
        Action   = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_table_arn
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
      Effect = "Allow"
      Principal = { Service = "batch.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_security_group" "worker" {
  name   = "pixel-worker-sg"
  vpc_id = var.vpc_id

  # container only needs to talk to postgres and aws apis
  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
    description = "postgres"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "aws apis (dynamodb, secrets manager, batch)"
  }

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

# Batch Compute Environment (Fargate Spot)
resource "aws_batch_compute_environment" "worker" {
  name                = "isofit-compute"
  type                = "MANAGED"
  service_role        = aws_iam_role.batch_service_role.arn

  compute_resources {
    type      = "FARGATE_SPOT"
    max_vcpus = 40 # 10 tasks * 4 vcpu each, adjust as needed

    subnets         = var.private_subnets
    security_group_ids = [aws_security_group.worker.id]
  }

  tags = var.tags
}

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

# Batch Job Definition
resource "aws_batch_job_definition" "worker" {
  name = "pixel-selection-worker"
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = var.ecr_image

    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }

    resourceRequirements = [
      { type = "VCPU",   value = "1" },
      { type = "MEMORY", value = "8192" }
    ]

    executionRoleArn = aws_iam_role.batch_execution_role.arn
    jobRoleArn       = aws_iam_role.batch_job_role.arn

    environment = [
      { name = "DB_SECRET_ARN",   value = var.db_secret_arn },
      { name = "DYNAMODB_TABLE",  value = var.dynamodb_table_name },
      { name = "AWS_REGION",      value = var.region },
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
    attempts = 2 # retry on spot interruption
  }

  timeout {
    attempt_duration_seconds = 900
  }

  tags = var.tags
}

# Cloudwatch log group
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/batch/pixel-worker"
  retention_in_days = 30

  tags = var.tags
}
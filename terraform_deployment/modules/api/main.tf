# -----------------------------
# IAM Role for Lambda
# -----------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "vswir-plants-database-api-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_secretsmanager_secret" "vswir_plants_db" {
  name        = "vswir_plants_db_credentials"
  description = "Database credentials for vswir plants api Lambda"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "vswir_plants_db_version" {
  secret_id = aws_secretsmanager_secret.vswir_plants_db.id
  secret_string = jsonencode({
    username = var.db_user
    password = var.db_user_password
    host     = var.db_host_url
    dbname   = var.db_name
    port     = var.db_port
  })

}


resource "aws_iam_policy" "lambda_secrets_policy" {
  name        = "vswir_plants_lambda_secrets_policy"
  description = "Allow Lambda to read DB credentials from Secrets Manager"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.vswir_plants_db.arn
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_secrets_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_secrets_policy.arn
}


resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_ecr_read" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_policy" "lambda_sqs_send_policy" {
  name = "vswir-plants-lambda-sqs-send-policy"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "sqs:SendMessage"
        ],
        Resource = aws_sqs_queue.export_queue.arn
      }
    ]
  })

  tags = var.tags
}
resource "aws_iam_role_policy_attachment" "lambda_sqs_send_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_sqs_send_policy.arn
}

resource "aws_security_group" "lambda_sg" {
  name        = "lambda-sg"
  description = "SG for Lambda in VPC"
  vpc_id      = var.vpc_id

  # No inbound rules needed — API Gateway triggers Lambda
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }


  # Outbound allows everything
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type = "Interface"

  # Enable Private DNS so your Lambda can use the standard endpoint name
  private_dns_enabled = true

  security_group_ids = [aws_security_group.lambda_sg.id]
  subnet_ids         = var.private_subnet_ids

  tags = var.tags
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"

  route_table_ids = var.route_table_ids

  tags = var.tags
}


resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  security_group_ids  = [aws_security_group.lambda_sg.id]
  subnet_ids          = var.private_subnet_ids
  tags                = var.tags
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  security_group_ids  = [aws_security_group.lambda_sg.id]
  subnet_ids          = var.private_subnet_ids
  tags                = var.tags
}

# -----------------------------
# Lambda function from ECR image
# -----------------------------
resource "aws_lambda_function" "vswir-plants" {
  function_name = "vswir-plants-database-api"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = var.ecr_image_url

  # VPC config for RDS access
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      DB_SECRET_ARN = aws_secretsmanager_secret.vswir_plants_db.arn
      SQS_QUEUE_URL = aws_sqs_queue.export_queue.url
    }
  }

  timeout     = 60       # seconds 900 max
  memory_size = 1024 * 2 # 1GB memory

  tags = var.tags
}

# -----------------------------
# API Gateway HTTP API
# -----------------------------
resource "aws_apigatewayv2_api" "vswir_plants" {
  name          = "${var.name}-gateway"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = [
      "http://localhost:3000",
      "https://plants.airborne.smce.nasa.gov"
    ]
    allow_methods = [
      "GET",
      "POST",
      "OPTIONS",
      "DELETE"
    ]
    allow_headers = [
      "content-type",
      "authorization"
    ]
    expose_headers = [
      "content-type"
    ]
    max_age = 3600
  }

  tags = var.tags
}

# Lambda integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.vswir_plants.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.vswir-plants.invoke_arn
  payload_format_version = "1.0"
}

# Cognito JWT authorizer for data routes
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.vswir_plants.id
  authorizer_type  = "JWT"
  name             = "cognito-authorizer"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_client_id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${var.cognito_user_pool_id}"
  }
}

resource "aws_apigatewayv2_route" "json_view" {
  api_id             = aws_apigatewayv2_api.vswir_plants.id
  route_key          = "GET /views/{view_name}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "json_view_post" {
  api_id             = aws_apigatewayv2_api.vswir_plants.id
  route_key          = "POST /views/{view_name}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.vswir_plants.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.vswir-plants.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.vswir_plants.execution_arn}/*/*"
}


resource "aws_s3_bucket" "vswir_plants_config" {
  bucket = "vswir-plants-config"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "vswir_plants_config" {
  bucket = aws_s3_bucket.vswir_plants_config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

}

resource "aws_s3_bucket_versioning" "vswir_plants_config" {
  bucket = aws_s3_bucket.vswir_plants_config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vswir_plants_config" {
  bucket = aws_s3_bucket.vswir_plants_config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_iam_policy" "lambda_vswir_plants_s3_read" {
  name = "lambda-vswir-plants-s3-read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # "*"
          "s3:GetObject"
        ]
        Resource = [aws_s3_bucket.vswir_plants_config.arn, "${aws_s3_bucket.vswir_plants_config.arn}/*"]
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_vswir_plants_s3_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_vswir_plants_s3_read.arn
}

resource "aws_s3_bucket_lifecycle_configuration" "vswir_plants_exports" {
  bucket = aws_s3_bucket.vswir_plants_config.id

  rule {
    id     = "expire_exports"
    status = "Enabled"

    filter { # replace 'prefix'
      prefix = "exports/"
    }

    expiration {
      days = 1
    }
  }
}

resource "aws_sqs_queue" "export_dlq" {
  name = "${var.name}-export-dlq"
  tags = var.tags
}

resource "aws_sqs_queue" "export_queue" {
  name                       = "${var.name}-export-queue"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.export_dlq.arn
    maxReceiveCount     = 3
  })

  tags = var.tags
}

resource "aws_vpc_endpoint" "sqs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.sqs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.lambda_sg.id]
  private_dns_enabled = true

  tags = var.tags
}


resource "aws_dynamodb_table" "export_jobs" {
  name         = "${var.name}-export-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }
  attribute {
    name = "parent_job_id"
    type = "S"
  }
  attribute {
    name = "job_type"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "parent_job_id-index"
    hash_key        = "parent_job_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "job_type-index"
    hash_key        = "job_type"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = var.tags
}

resource "aws_iam_role" "worker_lambda_role" {
  name = "vswir-plants-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })

  tags = var.tags
}

data "aws_iam_policy_document" "worker_lambda_policy_doc" {
  statement {
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [aws_sqs_queue.export_queue.arn]
  }

  statement {
    actions = [
      # "*"
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
      "s3:ListBucketMultipartUploads"
    ]
    resources = ["arn:aws:s3:::vswir-plants-config/*"]
  }

  statement {
    actions = [
      # "*"
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:GetItem"
    ]
    resources = [aws_dynamodb_table.export_jobs.arn]
  }

}


resource "aws_iam_policy" "worker_lambda_policy" {
  name   = "vswir-plants-worker-lambda-policy"
  policy = data.aws_iam_policy_document.worker_lambda_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "worker_lambda_policy_attach_worker" {
  role       = aws_iam_role.worker_lambda_role.name
  policy_arn = aws_iam_policy.worker_lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "worker_lambda_basic" {
  role       = aws_iam_role.worker_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_secrets_attach_worker" {
  role       = aws_iam_role.worker_lambda_role.name
  policy_arn = aws_iam_policy.lambda_secrets_policy.arn
}

resource "aws_iam_role_policy_attachment" "worker_vpc_access" {
  role       = aws_iam_role.worker_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}


resource "aws_lambda_function" "worker_lambda" {
  function_name = "vswir-plants-worker"
  role          = aws_iam_role.worker_lambda_role.arn
  package_type  = "Image"
  image_uri     = var.worker_lambda_url

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      S3_BUCKET     = aws_s3_bucket.vswir_plants_config.bucket
      JOB_TABLE     = aws_dynamodb_table.export_jobs.name
      DB_SECRET_ARN = aws_secretsmanager_secret.vswir_plants_db.arn
    }
  }

  timeout     = 900
  memory_size = 1024 * 3

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "worker_sqs_trigger" {
  event_source_arn = aws_sqs_queue.export_queue.arn
  function_name    = aws_lambda_function.worker_lambda.arn
  batch_size       = 1
  enabled          = true

  tags = var.tags
}


# -----------------------------
# IAM Role for Job Status Lambda
# -----------------------------
resource "aws_iam_role" "job_status_lambda_role" {
  name = "job-status-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "job_status_lambda_policy" {
  name = "job-status-lambda-policy"
  role = aws_iam_role.job_status_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.export_jobs.arn,
          "${aws_dynamodb_table.export_jobs.arn}/index/parent_job_id-index",
          "${aws_dynamodb_table.export_jobs.arn}/index/job_type-index",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "status_vpc_access" {
  role       = aws_iam_role.job_status_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# -----------------------------
# Job Status Lambda
# -----------------------------
resource "aws_lambda_function" "job_status" {
  function_name = "vswir-plants-job-status"
  role          = aws_iam_role.job_status_lambda_role.arn
  handler       = "app.main.lambda_handler"
  runtime       = "python3.11"

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  filename         = "${path.module}/job_status.zip"
  source_code_hash = filebase64sha256("${path.module}/job_status.zip")

  memory_size = 128
  timeout     = 10

  environment {
    variables = {
      JOB_TABLE = aws_dynamodb_table.export_jobs.name
    }
  }

  tags = var.tags
}

# -----------------------------
# API Gateway Integration
# -----------------------------
resource "aws_apigatewayv2_integration" "job_status" {
  api_id                 = aws_apigatewayv2_api.vswir_plants.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.job_status.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "job_status_route" {
  api_id             = aws_apigatewayv2_api.vswir_plants.id
  route_key          = "GET /job_status/{job_id}"
  target             = "integrations/${aws_apigatewayv2_integration.job_status.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "isofit_jobs_route" {
  api_id             = aws_apigatewayv2_api.vswir_plants.id
  route_key          = "GET /isofit_jobs"
  target             = "integrations/${aws_apigatewayv2_integration.job_status.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "job_status_apigw" {
  statement_id  = "AllowAPIGatewayInvokeJobStatus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.job_status.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.vswir_plants.execution_arn}/*/*"
}

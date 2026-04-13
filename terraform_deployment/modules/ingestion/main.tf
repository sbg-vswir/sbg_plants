# ── Shared Lambda security group ──────────────────────────────────────────────

resource "aws_security_group" "ingestion_lambda" {
  name   = "vswir-plants-ingestion-lambda-sg"
  vpc_id = var.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "aws apis"
  }

  tags = var.tags
}

resource "aws_security_group_rule" "ingestion_to_db" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ingestion_lambda.id
  source_security_group_id = var.db_security_group_id
}

# ── Secrets Manager secrets for DB users ──────────────────────────────────────

resource "aws_secretsmanager_secret" "staging_db" {
  name        = "ingestion_staging_credentials"
  description = "DB credentials for ingestion_staging user (vswir_plants_staging schema)"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "staging_db" {
  secret_id = aws_secretsmanager_secret.staging_db.id
  secret_string = jsonencode({
    username = var.ingestion_staging_user
    password = var.ingestion_staging_password
    host     = var.db_host
    dbname   = var.db_name
    port     = var.db_port
  })
}

resource "aws_secretsmanager_secret" "promotion_db" {
  name        = "ingestion_promotion_credentials"
  description = "DB credentials for ingestion_promotion user (staging → production)"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "promotion_db" {
  secret_id = aws_secretsmanager_secret.promotion_db.id
  secret_string = jsonencode({
    username = var.ingestion_promotion_user
    password = var.ingestion_promotion_password
    host     = var.db_host
    dbname   = var.db_name
    port     = var.db_port
  })
}

# ── IAM — Ingest Trigger ──────────────────────────────────────────────────────

resource "aws_iam_role" "ingest_trigger" {
  name = "vswir-plants-ingest-trigger-role"

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

resource "aws_iam_role_policy" "ingest_trigger" {
  role = aws_iam_role.ingest_trigger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${var.config_bucket_arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Query"]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/job_type-index",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.qaqc.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ingest_trigger_vpc" {
  role       = aws_iam_role.ingest_trigger.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ── IAM — QAQC ────────────────────────────────────────────────────────────────

resource "aws_iam_role" "qaqc" {
  name = "vswir-plants-qaqc-role"

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

resource "aws_iam_role_policy" "qaqc" {
  role = aws_iam_role.qaqc.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${var.config_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.config_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.staging_db.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "qaqc_vpc" {
  role       = aws_iam_role.qaqc.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ── IAM — Promotion ───────────────────────────────────────────────────────────

resource "aws_iam_role" "promotion" {
  name = "vswir-plants-promotion-role"

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

resource "aws_iam_role_policy" "promotion" {
  role = aws_iam_role.promotion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${var.config_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.promotion_db.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "promotion_vpc" {
  role       = aws_iam_role.promotion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ── IAM — Rejection ───────────────────────────────────────────────────────────

resource "aws_iam_role" "rejection" {
  name = "vswir-plants-rejection-role"

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

resource "aws_iam_role_policy" "rejection" {
  role = aws_iam_role.rejection.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.staging_db.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rejection_vpc" {
  role       = aws_iam_role.rejection.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ── Lambda functions ──────────────────────────────────────────────────────────

resource "aws_lambda_function" "ingest_trigger" {
  function_name = "vswir-plants-ingest-trigger"
  role          = aws_iam_role.ingest_trigger.arn
  package_type  = "Image"
  image_uri     = var.ingest_trigger_image_uri
  timeout       = 30
  memory_size   = 512

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.ingestion_lambda.id]
  }

  environment {
    variables = {
      CONFIG_BUCKET      = var.config_bucket_name
      JOB_TABLE          = var.dynamodb_table_name
      QAQC_FUNCTION_NAME = aws_lambda_function.qaqc.function_name
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "qaqc" {
  function_name = "vswir-plants-qaqc"
  role          = aws_iam_role.qaqc.arn
  package_type  = "Image"
  image_uri     = var.qaqc_image_uri
  timeout       = 900
  memory_size   = 3008

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.ingestion_lambda.id]
  }

  environment {
    variables = {
      CONFIG_BUCKET         = var.config_bucket_name
      JOB_TABLE             = var.dynamodb_table_name
      STAGING_DB_SECRET_ARN = aws_secretsmanager_secret.staging_db.arn
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "promotion" {
  function_name = "vswir-plants-promotion"
  role          = aws_iam_role.promotion.arn
  package_type  = "Image"
  image_uri     = var.promotion_image_uri
  timeout       = 300
  memory_size   = 1024

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.ingestion_lambda.id]
  }

  environment {
    variables = {
      JOB_TABLE               = var.dynamodb_table_name
      PROMOTION_DB_SECRET_ARN = aws_secretsmanager_secret.promotion_db.arn
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "rejection" {
  function_name = "vswir-plants-rejection"
  role          = aws_iam_role.rejection.arn
  package_type  = "Image"
  image_uri     = var.rejection_image_uri
  timeout       = 30
  memory_size   = 256
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.ingestion_lambda.id]
  }
  environment {
    variables = {
      JOB_TABLE             = var.dynamodb_table_name
      STAGING_DB_SECRET_ARN = aws_secretsmanager_secret.staging_db.arn
    }
  }
  tags = var.tags
}

# ── Lambda permissions ────────────────────────────────────────────────────────

resource "aws_lambda_permission" "ingest_trigger_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest_trigger.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

resource "aws_lambda_permission" "promotion_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.promotion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

resource "aws_lambda_permission" "rejection_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rejection.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

# ── API Gateway routes ────────────────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "ingest_trigger" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ingest_trigger.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "promotion" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.promotion.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "rejection" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.rejection.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_ingest_upload_urls" {
  api_id             = var.api_id
  route_key          = "POST /ingest/upload-urls"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "get_ingest_file_upload_url" {
  api_id             = var.api_id
  route_key          = "GET /ingest/{batch_id}/file/{slot}/upload-url"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "post_ingest" {
  api_id             = var.api_id
  route_key          = "POST /ingest"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "get_ingest_config" {
  api_id             = var.api_id
  route_key          = "GET /ingest/config"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "get_ingest" {
  api_id             = var.api_id
  route_key          = "GET /ingest"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "get_ingest_batch" {
  api_id             = var.api_id
  route_key          = "GET /ingest/{batch_id}"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "put_ingest_file" {
  api_id             = var.api_id
  route_key          = "PUT /ingest/{batch_id}/file/{slot}"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "post_ingest_recheck" {
  api_id             = var.api_id
  route_key          = "POST /ingest/{batch_id}/recheck"
  target             = "integrations/${aws_apigatewayv2_integration.ingest_trigger.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "approve" {
  api_id             = var.api_id
  route_key          = "POST /ingest/{batch_id}/approve"
  target             = "integrations/${aws_apigatewayv2_integration.promotion.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "reject" {
  api_id             = var.api_id
  route_key          = "POST /ingest/{batch_id}/reject"
  target             = "integrations/${aws_apigatewayv2_integration.rejection.id}"
  authorizer_id      = var.cognito_authorizer_id
  authorization_type = "JWT"
}

# ── CloudWatch log groups ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "ingest_trigger" {
  name              = "/aws/lambda/vswir-plants-ingest-trigger"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "qaqc" {
  name              = "/aws/lambda/vswir-plants-qaqc"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "promotion" {
  name              = "/aws/lambda/vswir-plants-promotion"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "rejection" {
  name              = "/aws/lambda/vswir-plants-rejection"
  retention_in_days = 30
  tags              = var.tags
}

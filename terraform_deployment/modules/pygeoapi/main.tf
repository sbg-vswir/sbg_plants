# -----------------------------
# IAM Role for Lambda
# -----------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "pygeoapi-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_secretsmanager_secret" "pygeoapi_db" {
  name        = "pygeoapi_db_credentials"
  description = "Database credentials for pygeoapi Lambda"
}

resource "aws_secretsmanager_secret_version" "pygeoapi_db_version" {
  secret_id     = aws_secretsmanager_secret.pygeoapi_db.id
  secret_string = jsonencode({
    username = var.db_user
    password = var.db_user_password
    host     = var.db_host_url
    dbname   = var.db_name
    port     = var.db_port
  })
}


resource "aws_iam_policy" "lambda_secrets_policy" {
  name        = "pygeoapi_lambda_secrets_policy"
  description = "Allow Lambda to read DB credentials from Secrets Manager"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.pygeoapi_db.arn
      }
    ]
  })
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
}

#resource "aws_security_group" "lambda_sg" {
#  name        = "lambda-sg"
#  description = "SG for Lambda in VPC"
#  vpc_id      = var.vpc_id
#
#  ingress {
#    from_port   = 443
#    to_port     = 443
#    protocol    = "tcp"
#    cidr_blocks = ["0.0.0.0/0"]
#  }
#
#  egress {
#    from_port   = 443
#    to_port     = 443
#    protocol    = "tcp"
#    cidr_blocks = ["0.0.0.0/0"]
#  }
#}


resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type = "Interface"

  # Enable Private DNS so your Lambda can use the standard endpoint name
  private_dns_enabled = true

  security_group_ids = [aws_security_group.lambda_sg.id]
  subnet_ids        = var.public_subnet_ids
}

# -----------------------------
# Lambda function from ECR image
# -----------------------------
resource "aws_lambda_function" "pygeoapi" {
  function_name = "pygeoapi-lambda"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = var.ecr_image_url

  # VPC config for RDS access
  vpc_config {
    subnet_ids         = var.public_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      DB_SECRET_ARN = aws_secretsmanager_secret.pygeoapi_db.arn
    }
  }

  timeout = 60  # seconds 900 max
  memory_size = 1024 * 2 # 1GB memory
}

# -----------------------------
# API Gateway HTTP API
# -----------------------------
resource "aws_apigatewayv2_api" "pygeoapi" {
  name          = "${var.name}-gateway"
  protocol_type = "HTTP"
}

# Lambda integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.pygeoapi.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.pygeoapi.invoke_arn
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_route" "json_view" {
  api_id    = aws_apigatewayv2_api.pygeoapi.id
  route_key = "GET /views/{view_name}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.pygeoapi.id
  name        = "$default"    # special default stage
  auto_deploy = true
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pygeoapi.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.pygeoapi.execution_arn}/*/*"
}


resource "aws_s3_bucket" "pygeoapi_config" {
  bucket = "pygeoapi-config"
}

resource "aws_s3_bucket_public_access_block" "pygeoapi_config" {
  bucket = aws_s3_bucket.pygeoapi_config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "pygeoapi_config" {
  bucket = aws_s3_bucket.pygeoapi_config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pygeoapi_config" {
  bucket = aws_s3_bucket.pygeoapi_config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_iam_policy" "lambda_pygeoapi_s3_read" {
  name = "lambda-pygeoapi-s3-read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "*"
          #"s3:GetObject"
        ]
        Resource = ["arn:aws:s3:::pygeoapi-config", "arn:aws:s3:::pygeoapi-config/*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_pygeoapi_s3_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_pygeoapi_s3_read.arn
}

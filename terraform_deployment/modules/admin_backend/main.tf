# admin_users.tf

locals {
  admin_zip = "${path.module}/admin_users.zip"
}

# ── IAM ──────────────────────────────────────────────────────────────

resource "aws_iam_role" "admin_users_lambda_role" {
  name = "admin-users-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "admin_users_basic_execution" {
  role       = aws_iam_role.admin_users_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "admin_users_cognito" {
  name = "admin-users-cognito-policy"
  role = aws_iam_role.admin_users_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cognito-idp:ListUsers",
        "cognito-idp:AdminListGroupsForUser",
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminDeleteUser",
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminRemoveUserFromGroup"
      ]
      Resource = var.cognito_user_pool_arn
    }]
  })
}

# ── Lambda ────────────────────────────────────────────────────────────

resource "aws_lambda_function" "admin_users" {
  function_name    = "admin-users-lambda"
  role             = aws_iam_role.admin_users_lambda_role.arn
  handler          = "app.main.handler"
  runtime          = "python3.11"

  filename         = local.admin_zip
  source_code_hash = filebase64sha256(local.admin_zip)

  memory_size = 128
  timeout     = 30  # higher than yours since list_users fans out per user

  environment {
    variables = {
      COGNITO_USER_POOL_ID = var.cognito_user_pool_id
    }
  }
}

resource "aws_lambda_permission" "admin_users_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.admin_users.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_execution_arn}/*"
}

# ── Cognito Authorizer ────────────────────────────────────────────────

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = var.api_id
  authorizer_type  = "JWT"
  name             = "cognito-authorizer"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_client_id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${var.cognito_user_pool_id}"
  }
}

# ── Routes ────────────────────────────────────────────────────────────

locals {
  admin_lambda_integration_id = aws_apigatewayv2_integration.admin_users.id
  authorizer_id               = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_integration" "admin_users" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.admin_users.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_admin_users" {
  api_id             = var.api_id
  route_key          = "GET /admin/users"
  target             = "integrations/${local.admin_lambda_integration_id}"
  authorizer_id      = local.authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "post_admin_users" {
  api_id             = var.api_id
  route_key          = "POST /admin/users"
  target             = "integrations/${local.admin_lambda_integration_id}"
  authorizer_id      = local.authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "delete_admin_user" {
  api_id             = var.api_id
  route_key          = "DELETE /admin/users/{username}"
  target             = "integrations/${local.admin_lambda_integration_id}"
  authorizer_id      = local.authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "post_admin_user_group" {
  api_id             = var.api_id
  route_key          = "POST /admin/users/{username}/groups"
  target             = "integrations/${local.admin_lambda_integration_id}"
  authorizer_id      = local.authorizer_id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "delete_admin_user_group" {
  api_id             = var.api_id
  route_key          = "DELETE /admin/users/{username}/groups/{group}"
  target             = "integrations/${local.admin_lambda_integration_id}"
  authorizer_id      = local.authorizer_id
  authorization_type = "JWT"
}
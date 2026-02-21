# variables.tf — add these to your existing variables

variable "cognito_user_pool_id" {
  type        = string
  description = "Cognito User Pool ID"
}

variable "cognito_user_pool_arn" {
  type        = string
  description = "Cognito User Pool ARN"
}

variable "cognito_client_id" {
  type        = string
  description = "Cognito App Client ID"
}

variable "aws_region" {
  type = string
}

variable "api_id" {
  type = string
}

variable "api_execution_arn" {
  type        = string
  description = "Execution ARN of the API Gateway HTTP API"
}
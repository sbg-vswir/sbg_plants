variable "ecr_image_url" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "route_table_ids" {
  type = list(string)
}

variable "name" {
  type = string
}

variable "vpc_id" {
  description = "vpc_id"
  type        = string
}

variable "db_user" {
  type = string
}

variable "db_user_password" {
  type = string
}

variable "db_host_url" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_port" {
  type = string
}

variable "region" {
  type = string
}

variable "worker_lambda_url" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for JWT authorizer"
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito App Client ID for JWT authorizer audience"
  type        = string
}
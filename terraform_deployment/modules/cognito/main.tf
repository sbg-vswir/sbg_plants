#########################
# Provider
#########################
provider "aws" {
  region = var.aws_region
}

#########################
# Variables
#########################
variable "aws_region" {
  description = "AWS region to deploy Cognito resources"
  type        = string
  default     = "us-west-2"
}

variable "spa_domain" {
  description = "Full domain of the SPA (used for callback and logout URLs)"
  type        = string
  default     = "https://plants.airborne.smce.nasa.gov"
}

variable "spa_callback_path" {
  description = "Path on the SPA that Cognito redirects to after login"
  type        = string
  # default     = "/auth/callback"
  default = ""
}

variable "user_pool_name" {
  description = "Name of the Cognito User Pool"
  type        = string
  default     = "vswir-plants-user-pool"
}

variable "user_pool_client_name" {
  description = "Name of the Cognito User Pool Client"
  type        = string
  default     = "vswir-spa-client"
}

variable "use_random_suffix" {
  description = "Append a random suffix to the Cognito Hosted UI domain for uniqueness"
  type        = bool
  default     = true
}

variable "local_dev_domain" {
  description = "Local development URL for testing (leave empty to disable)"
  type        = string
  default     = "http://localhost:3000"
}

#########################
# Locals
#########################
locals {
  callback_url       = "${var.spa_domain}${var.spa_callback_path}"
  local_callback_url = var.local_dev_domain != "" ? "${var.local_dev_domain}${var.spa_callback_path}" : null
  cognito_base       = "https://vswir-plants-auth${var.use_random_suffix ? "-${random_id.suffix[0].hex}" : ""}.auth.${var.aws_region}.amazoncognito.com"
  encoded_callback   = replace(replace(replace(local.callback_url, ":", "%3A"), "/", "%2F"), ".", "%2E")

  all_callback_urls = compact([local.callback_url, local.local_callback_url])
  all_logout_urls   = compact([var.spa_domain, var.local_dev_domain])
}

#########################
# Random suffix (optional)
#########################
resource "random_id" "suffix" {
  count       = var.use_random_suffix ? 1 : 0
  byte_length = 3
}

#########################
# Cognito User Pool
#########################
resource "aws_cognito_user_pool" "vswir_user_pool" {
  name = var.user_pool_name

  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = {
    Project = "VSWIR Plants"
  }

  lifecycle {
    prevent_destroy = true
  }
}

#########################
# Cognito User Pool Client (SPA)
#########################
resource "aws_cognito_user_pool_client" "vswir_spa_client" {
  name         = var.user_pool_client_name
  user_pool_id = aws_cognito_user_pool.vswir_user_pool.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  supported_identity_providers = ["COGNITO"]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  callback_urls = local.all_callback_urls
  logout_urls   = local.all_logout_urls

  token_validity_units {
    access_token  = "minutes"
    refresh_token = "days"
    id_token      = "minutes"
  }

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 1
}

#########################
# Cognito Hosted UI Domain
#########################
resource "aws_cognito_user_pool_domain" "vswir_domain" {
  domain       = "vswir-plants-auth${var.use_random_suffix ? "-${random_id.suffix[0].hex}" : ""}"
  user_pool_id = aws_cognito_user_pool.vswir_user_pool.id
}

#########################
# Outputs
#########################
output "user_pool_id" {
  value = aws_cognito_user_pool.vswir_user_pool.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.vswir_spa_client.id
}

output "cognito_domain" {
  value = local.cognito_base
}

output "callback_url" {
  description = "The exact redirect_uri your SPA must send in the auth request"
  value       = local.callback_url
}

output "login_url" {
  description = "Direct link to the Cognito hosted UI login page"
  value       = "${local.cognito_base}/login?client_id=${aws_cognito_user_pool_client.vswir_spa_client.id}&response_type=code&scope=openid%20email%20profile&redirect_uri=${local.encoded_callback}"
}

output "logout_url" {
  description = "Direct link to the Cognito hosted UI logout endpoint"
  value       = "${local.cognito_base}/logout?client_id=${aws_cognito_user_pool_client.vswir_spa_client.id}&logout_uri=${var.spa_domain}"
}

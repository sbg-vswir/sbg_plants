
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
# Your single user pool
resource "aws_cognito_user_pool" "vswir_user_pool" {
  name = "vswir-user-pool"

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

  tags = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

# Groups inside that user pool
resource "aws_cognito_user_group" "users" {
  name         = "users"
  user_pool_id = aws_cognito_user_pool.vswir_user_pool.id
  precedence   = 10
}

resource "aws_cognito_user_group" "admins" {
  name         = "admins"
  user_pool_id = aws_cognito_user_pool.vswir_user_pool.id
  precedence   = 2
}

resource "aws_cognito_user_group" "superadmins" {
  name         = "superadmins"
  user_pool_id = aws_cognito_user_pool.vswir_user_pool.id
  precedence   = 1
}

#########################
# Cognito User Pool Client (SPA)
#########################
resource "aws_cognito_user_pool_client" "vswir_spa_client" {
  name         = "vswir-spa-client"
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

output "user_pool_id" {
  value = aws_cognito_user_pool.vswir_user_pool.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.vswir_spa_client.id
}

output "cognito_domain" {
  value = local.cognito_base
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.vswir_user_pool.arn
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

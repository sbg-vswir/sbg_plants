output "api_id" {
  value = aws_apigatewayv2_api.vswir_plants.id
}

output "api_execution_arn" {
  value = aws_apigatewayv2_api.vswir_plants.execution_arn
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.vswir_plants_db.arn
}

output "export_jobs_table_arn" {
  value = aws_dynamodb_table.export_jobs.arn
}

output "export_jobs_table_name" {
  value = aws_dynamodb_table.export_jobs.name
}

output "cognito_authorizer_id" {
  value = aws_apigatewayv2_authorizer.cognito.id
}

output "spa_bucket_name" {
  value = aws_s3_bucket.vswir_plants_config.id
}
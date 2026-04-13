variable "region" {
  default = "us-west-2"
}

variable "vpc_id" {}

variable "private_subnet_ids" {
  type = list(string)
}

variable "api_id" {
  description = "API Gateway ID"
}

variable "api_execution_arn" {
  description = "API Gateway execution ARN"
  type        = string
}

variable "cognito_authorizer_id" {
  description = "Cognito JWT authorizer ID"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the shared export-jobs DynamoDB table"
}

variable "dynamodb_table_name" {
  description = "Name of the shared export-jobs DynamoDB table"
}

variable "config_bucket_name" {
  description = "S3 bucket name for ingestion files and QAQC reports"
}

variable "config_bucket_arn" {
  description = "S3 bucket ARN"
}

variable "db_security_group_id" {
  description = "Security group of the RDS instance"
}

variable "ingestion_staging_user" {
  description = "Username for the ingestion_staging DB user"
  type        = string
}

variable "ingestion_staging_password" {
  description = "Password for the ingestion_staging DB user"
  type        = string
  sensitive   = true
}

variable "ingestion_promotion_user" {
  description = "Username for the ingestion_promotion DB user"
  type        = string
}

variable "ingestion_promotion_password" {
  description = "Password for the ingestion_promotion DB user"
  type        = string
  sensitive   = true
}

variable "db_host" {
  description = "RDS instance endpoint"
  type        = string
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_port" {
  description = "Database port"
  type        = string
  default     = "5432"
}

variable "ingest_trigger_image_uri" {
  description = "ECR image URI for the ingest trigger Lambda"
}

variable "qaqc_image_uri" {
  description = "ECR image URI for the QAQC Lambda"
}

variable "promotion_image_uri" {
  description = "ECR image URI for the promotion Lambda"
}

variable "rejection_image_uri" {
  description = "ECR image URI for the rejection Lambda"
}

variable "tags" {
  type = map(string)
}

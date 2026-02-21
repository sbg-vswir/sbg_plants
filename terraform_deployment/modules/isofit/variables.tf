variable "region" {
  default = "us-west-2"
}

variable "vpc_id" {}
variable "private_subnets" {
  type = list(string)
}

variable "public_subnets" {
  type = list(string)
}

variable "ecr_image" {
  description = "ECR image URI for worker"
}

variable "db_security_group_id" {
  description = "Security group of database to allow access"
}
variable "api_id" {
  description = "API Gateway ID for Lambda integration"
}
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
variable "db_secret_arn"       {}
variable "dynamodb_table_arn"  {}
variable "dynamodb_table_name" {}
variable "vpc_cidr_block" {
  description = "VPC cidr for subnets to be inside of"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all network resource"
  type        = map(string)
}

variable "isofit_user_password" {
  description = "password for isofit user"
  type        = string
}

variable "isofit_user" {
  description = "username for isofit user"
  type        = string
}

variable "db_port" {
    description = "port for postgres db"
    type        = string
}

variable "db_host_url" {
    description = "host url for postgres db"
    type        = string
}

variable "db_name" {
  description = "name of postgres db"
  type        = string
}

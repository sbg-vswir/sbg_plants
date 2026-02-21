variable "name" {
  description = "Prefix name to give to network resources"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all network resource"
  type        = map(string)
}

variable "vpc_cidr_block" {
  description = "VPC cidr for subnets to be inside of"
  type        = string
}

variable "db_password" {
  description = "password for postgres db"
  type        = string
}

variable "db_port" {
    description = "port for postgres db"
    type        = string
}


variable "aws_availability_zones" {
  description = "AWS Availability zones to operate infrastructure"
  type        = list(string)
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "db_name" {
    description = "name of the postgres db"
    type        = string
}

variable "ecr_image_url" {
    type  = string
}

variable "worker_lambda_url" {
    type  = string
}

variable "db_user" {
    type  = string
}

variable "db_user_password" {
    type  = string
}

variable "spa_domain" {
  description = "Full domain of the SPA (used for callback and logout URLs)"
  type        = string
}
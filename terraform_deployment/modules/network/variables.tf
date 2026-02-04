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

variable "aws_availability_zones" {
  description = "AWS Availability zones to operate infrastructure"
  type        = list(string)
}

variable "region" {
  description = "AWS region"
  type        = string
}

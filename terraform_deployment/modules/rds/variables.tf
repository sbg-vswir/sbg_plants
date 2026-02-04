variable "vpc_id" {
  description = "vpc_id"
  type        = string
}

variable "name" {
  description = "Prefix name to give to network resources"
  type        = string
}

variable "vpc_cidr_block" {
  description = "vpc cidr block"
  type        = string
}

variable "private_subnet_ids" {
  description = "AWS VPC subnets to use for efs"
  type        = list(string)
}

variable "db_password" {
  description = "password for postgres db"
  type        = string
}

variable "db_port" {
    description = "port for postgres db"
    type        = string
}

variable "tags" {
  description = "Additional tags to apply to all network resource"
  type        = map(string)
}

variable "db_name" {
    description = "name of the postgres db"
    type        = string
}
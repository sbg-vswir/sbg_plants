variable "ecr_image_url" {
    type  = string
}

variable "public_subnet_ids" {
    type  = list(string)
}

variable "name" {
    type  = string
}

variable "vpc_id" {
  description = "vpc_id"
  type        = string
}

variable "db_user" {
    type  = string
}

variable "db_user_password" {
    type  = string
}

variable "db_host_url" {
    type  = string
}

variable "db_name" {
    type  = string
}

variable "db_port" {
    type  = string
}

variable "region" {
    type  = string
}
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "spa_bucket_name" {
  description = "Existing S3 bucket for SPA"
  type        = string
  default     = "pygeoapi-config"
}

variable "spa_subdomain" {
  description = "Full subdomain for the SPA, e.g. plants.airborne.smce.nasa.gov"
  type        = string
}

variable "root_domain" {
  description = "Root domain for ACM cert and Route53 zone lookup, e.g. airborne.smce.nasa.gov"
  type        = string
}

variable "dist_dir" {
  description = "Local path to the SPA build output folder"
  type        = string
  default     = "dist"
}
variable "tags" {
  type = map(string) 
}
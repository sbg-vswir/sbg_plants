variable "aws_region" {
  description = "AWS region to deploy Cognito resources"
  type        = string
}

variable "spa_domain" {
  description = "Full domain of the SPA (used for callback and logout URLs)"
  type        = string
  default     = "https://plants.airborne.smce.nasa.gov"
}

variable "spa_callback_path" {
  description = "Path on the SPA that Cognito redirects to after login"
  type        = string
  # default     = "/auth/callback"
  default = ""
}

variable "use_random_suffix" {
  description = "Append a random suffix to the Cognito Hosted UI domain for uniqueness"
  type        = bool
  default     = true
}

variable "local_dev_domain" {
  description = "Local development URL for testing (leave empty to disable)"
  type        = string
  default     = "http://localhost:3000"
}
variable "name" {
  description = "Prefix name to give to network resources"
  type        = string 
}
variable "tags" {
    description = "Additional tags to apply to all network resource"
    type        = map(string)
}
terraform {
  backend "s3" {
    bucket       = "vswir-plants-database-tf-state"
    key          = "global/sbg_plants/terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
    encrypt      = true
    profile      = "smce-airborne"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

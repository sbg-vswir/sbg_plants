terraform {
  backend "s3" {
    bucket         = "vswir-plants-database-tf-state"
    key            = "global/sbg_plants/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "vswir-plants-database-tf-state-state-locks"
    encrypt        = true
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
    # profile = "smce-airborne"
    region = "us-west-2"
}
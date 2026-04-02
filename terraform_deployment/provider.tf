provider "aws" {
  profile = "smce-airborne"
  region  = "us-west-2"
}

# Required for CloudFront ACM certificates
provider "aws" {
  alias   = "us_east_1"
  profile = "smce-airborne"
  region  = "us-east-1"
}
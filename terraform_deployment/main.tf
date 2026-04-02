locals {
  private_subnet_ids = ["subnet-06884e5beb7fd2f8b", "subnet-0733fed6dff9e9f29"]
  public_subnet_ids  = ["subnet-06e3c65ef2d8b1ab5", "subnet-010fd428a087044e7"]
}

module "network" {

  source = "./modules/network"

  name                   = var.name
  region                 = var.region
  aws_availability_zones = var.aws_availability_zones
  tags                   = var.tags
  vpc_cidr_block         = var.vpc_cidr_block
  bastion_public_key     = var.bastion_public_key

}

module "rds" {

  source = "./modules/rds"

  vpc_id             = module.network.vpc_id
  vpc_cidr_block     = var.vpc_cidr_block
  private_subnet_ids = local.private_subnet_ids
  db_password        = var.db_password
  db_port            = var.db_port
  name               = var.name
  tags               = var.tags
  db_name            = var.db_name

}

module "api" {

  source = "./modules/api"

  vpc_id             = module.network.vpc_id
  public_subnet_ids  = local.public_subnet_ids
  private_subnet_ids = local.private_subnet_ids
  name               = var.name
  ecr_image_url      = var.ecr_image_url
  worker_lambda_url  = var.worker_lambda_url

  route_table_ids  = module.network.vpc_route_table_ids
  db_port          = var.db_port
  db_name          = var.db_name
  db_user          = var.db_user
  db_user_password = var.db_user_password
  db_host_url      = module.rds.db_instance_endpoint
  region           = var.region
  tags             = var.tags

  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_client_id    = module.cognito.user_pool_client_id
}

module "cognito" {

  source = "./modules/cognito"

  aws_region = var.region
  spa_domain = var.spa_domain
  name       = var.name
  tags       = var.tags

}

module "frontend" {

  source          = "./modules/frontend"
  aws_region      = var.region
  spa_subdomain   = replace(var.spa_domain, "https://", "")
  root_domain     = replace(replace(var.spa_domain, "https://", ""), "plants.", "")
  tags            = var.tags
  spa_bucket_name = module.api.spa_bucket_name

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

module "admin_backend" {

  source = "./modules/admin_backend"

  aws_region            = var.region
  api_id                = module.api.api_id
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_client_id     = module.cognito.user_pool_client_id
  cognito_user_pool_arn = module.cognito.user_pool_arn
  api_execution_arn     = module.api.api_execution_arn
  tags                  = var.tags
}

module "isofit_pipeline" {
  source                    = "./modules/isofit_pipeline"
  vpc_id                    = module.network.vpc_id
  vpc_cidr_block            = var.vpc_cidr_block
  private_subnets           = local.private_subnet_ids
  public_subnets            = local.public_subnet_ids
  api_id                    = module.api.api_id
  db_security_group_id      = module.rds.db_security_group_id
  db_secret_arn             = module.api.db_secret_arn
  dynamodb_table_arn        = module.api.export_jobs_table_arn
  dynamodb_table_name       = module.api.export_jobs_table_name
  ecr_image                 = var.isofit_ecr_image
  isofit_ami_id             = var.isofit_ami_id
  pixel_selection_ecr_image = var.pixel_selection_ecr_image
  cognito_authorizer_id     = module.api.cognito_authorizer_id
  api_execution_arn         = module.api.api_execution_arn
  isofit_user               = var.isofit_user
  isofit_user_password      = var.isofit_user_password
  db_port                   = var.db_port
  db_host_url               = module.rds.db_instance_endpoint
  db_name                   = var.db_name
  region                    = var.region
  tags                      = var.tags
}

module "network" {

  source                 = "./modules/network"

  name                   = var.name
  region                 = var.region
  aws_availability_zones = var.aws_availability_zones
  tags                   = var.tags
  vpc_cidr_block         = var.vpc_cidr_block

}

module "rds" {

  source                 = "./modules/rds"

  vpc_id = module.network.vpc_id
  vpc_cidr_block = var.vpc_cidr_block
  private_subnet_ids = module.network.subnet_private_ids
  db_password = var.db_password
  db_port = var.db_port
  name = var.name
  tags    = var.tags
  db_name = var.db_name


}

module "pygeoapi" {

  source                 = "./modules/pygeoapi"

  vpc_id             = module.network.vpc_id
  public_subnet_ids = module.network.subnet_public_ids
  name               = var.name
  ecr_image_url      = var.ecr_image_url
  worker_lambda_url   = var.worker_lambda_url

  route_table_ids = module.network.vpc_route_table_ids
  db_port = var.db_port
  db_name = var.db_name
  db_user = var.db_user
  db_user_password = var.db_user_password
  db_host_url = module.rds.db_instance_endpoint
  region = var.region
}
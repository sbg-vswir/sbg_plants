output "db_instance_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "db_instance_username" {
  value = module.rds.db_instance_username
}

output "db_instance_id" {
  value = module.rds.db_instance_id
}

output "subnet_public_ids" {
  value = module.network.subnet_public_ids
}

output "subnet_private_ids" {
  value = module.network.subnet_private_ids
}
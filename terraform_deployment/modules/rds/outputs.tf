output "db_instance_endpoint" {
  value = aws_db_instance.default.address
}

output "db_instance_username" {
  value = aws_db_instance.default.username
}

output "db_instance_id" {
  value = aws_db_instance.default.id
}

output "db_security_group_id" {
  value = aws_security_group.database_sg.id
}

output "db_instance_endpoint" {
  value = aws_db_instance.default.address
}

output "db_instance_username" {
  value = aws_db_instance.default.username
}

output "db_instance_id" {
  value = aws_db_instance.default.id
}

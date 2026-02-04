output "vpc_id" {
  description = "AWS VPC id"
  value       = aws_vpc.main.id
}

output "subnet_public_ids" {
  description = "AWS VPC subnet ids"
  value       = aws_subnet.public[*].id
}

output "subnet_private_ids" {
  description = "AWS VPC subnet ids"
  value       = aws_subnet.private[*].id
}

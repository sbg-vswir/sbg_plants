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

output "vpc_route_table_ids" {
  description = "All route table IDs in the VPC (main + private route tables)"
  value = concat(
    [aws_vpc.main.main_route_table_id],  # Main route table for public subnets
    aws_route_table.private[*].id       # Private route tables
  )
}

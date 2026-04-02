output "vpc_id" {
  description = "AWS VPC id"
  value       = aws_vpc.main.id
}

output "subnet_public_ids" {
  description = "Public subnet IDs"
  value       = ["subnet-06e3c65ef2d8b1ab5", "subnet-010fd428a087044e7"]
}

output "subnet_private_ids" {
  description = "Private subnet IDs"
  value       = ["subnet-06884e5beb7fd2f8b", "subnet-0733fed6dff9e9f29"]
}

output "vpc_route_table_ids" {
  description = "All route table IDs in the VPC (main + private route tables)"
  value = concat(
    [aws_vpc.main.main_route_table_id],
    aws_route_table.private[*].id
  )
}

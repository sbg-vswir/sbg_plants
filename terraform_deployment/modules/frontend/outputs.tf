output "cloudfront_domain" {
  value = aws_cloudfront_distribution.spa_cdn.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.spa_cdn.id
}

output "spa_url" {
  value = "https://${var.spa_subdomain}"
}

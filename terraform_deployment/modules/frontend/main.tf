#########################
# Locals
#########################
locals {
  # Content-type map used for S3 uploads
  content_type_map = {
    ".html"  = "text/html; charset=utf-8"
    ".js"    = "application/javascript"
    ".mjs"   = "application/javascript"
    ".css"   = "text/css"
    ".json"  = "application/json"
    ".svg"   = "image/svg+xml"
    ".png"   = "image/png"
    ".jpg"   = "image/jpeg"
    ".jpeg"  = "image/jpeg"
    ".gif"   = "image/gif"
    ".webp"  = "image/webp"
    ".ico"   = "image/x-icon"
    ".woff"  = "font/woff"
    ".woff2" = "font/woff2"
    ".ttf"   = "font/ttf"
    ".txt"   = "text/plain"
    ".xml"   = "application/xml"
    ".map"   = "application/json"
  }

  files = fileset("${path.module}/${var.dist_dir}", "**")

  # Derive content type from file extension; fall back to octet-stream
  file_content_types = {
    for f in local.files : f => lookup(
      local.content_type_map,
      # extract extension including the dot, lowercase
      length(regexall("(\\.[^./]+)$", f)) > 0
        ? lower(regexall("(\\.[^./]+)$", f)[0][0])
        : "",
      "application/octet-stream"
    )
  }
}

#########################
# Existing S3 bucket
#########################
data "aws_s3_bucket" "spa_bucket" {
  bucket = var.spa_bucket_name
}

#########################
# S3 bucket policy — grants CloudFront OAC read access
#########################
data "aws_iam_policy_document" "spa_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.spa_bucket.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.spa_cdn.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "spa_bucket_policy" {
  bucket = data.aws_s3_bucket.spa_bucket.id
  policy = data.aws_iam_policy_document.spa_bucket_policy.json
}

#########################
# ACM certificate (must be us-east-1 for CloudFront)
#########################
resource "aws_acm_certificate" "domain_cert_us_east_1" {
  provider          = aws.us_east_1
  domain_name       = var.root_domain
  subject_alternative_names = ["*.${var.root_domain}"]
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.domain_cert_us_east_1.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  allow_overwrite = true   # add this
  zone_id = data.aws_route53_zone.zone.id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "domain_cert_us_east_1" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.domain_cert_us_east_1.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

#########################
# Route53 hosted zone
#########################
data "aws_route53_zone" "zone" {
  name         = "${var.root_domain}."
  private_zone = false
}

#########################
# CloudFront OAC
#########################
resource "aws_cloudfront_origin_access_control" "spa_oac" {
  name                      = "${var.spa_subdomain}-oac"
  origin_access_control_origin_type = "s3"
  signing_protocol          = "sigv4"
  signing_behavior          = "always"
}

#########################
# CloudFront distribution
#########################
resource "aws_cloudfront_distribution" "spa_cdn" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = [var.spa_subdomain]
  price_class         = "PriceClass_100" # US/EU only — remove if you need global

  origin {
    domain_name              = data.aws_s3_bucket.spa_bucket.bucket_regional_domain_name
    origin_id                = "spaS3Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.spa_oac.id
    # No s3_origin_config block — that's the old OAI pattern, incompatible with OAC
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "spaS3Origin"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    # Cache JS/CSS aggressively; index.html should be short-lived
    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # Short cache for HTML so deploys propagate quickly
  ordered_cache_behavior {
    path_pattern           = "*.html"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "spaS3Origin"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 60
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.domain_cert_us_east_1.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  # Both 403 and 404 must be caught — S3+OAC returns 403 for missing objects
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Project = "VSWIR Plants"
  }
}

#########################
# Route53 alias record
#########################
resource "aws_route53_record" "spa_alias" {
  zone_id = data.aws_route53_zone.zone.id
  name    = var.spa_subdomain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.spa_cdn.domain_name
    zone_id                = aws_cloudfront_distribution.spa_cdn.hosted_zone_id
    evaluate_target_health = false
  }
}

#########################
# S3 file uploads
#########################
resource "aws_s3_object" "spa_files" {
  for_each = local.file_content_types

  bucket       = data.aws_s3_bucket.spa_bucket.id
  key          = each.key
  source       = "${path.module}/${var.dist_dir}/${each.key}"
  etag         = filemd5("${path.module}/${var.dist_dir}/${each.key}")
  content_type = each.value
  # No acl = "private" — modern buckets have ACLs disabled by default;
  # access is controlled entirely via the bucket policy above
}

#########################
# Cache invalidation via local-exec
# (aws_cloudfront_distribution_invalidation is not a real resource)
#########################
resource "null_resource" "spa_invalidate" {
  triggers = {
    # Re-runs whenever any file etag changes
    file_etags = join(",", [for f, _ in local.file_content_types : filemd5("${path.module}/${var.dist_dir}/${f}")])
  }

  depends_on = [aws_s3_object.spa_files]

  provisioner "local-exec" {
    command = <<-EOT
      aws cloudfront create-invalidation \
        --distribution-id ${aws_cloudfront_distribution.spa_cdn.id} \
        --paths "/*"
    EOT
  }
}

#########################
# Outputs
#########################
output "cloudfront_domain" {
  value = aws_cloudfront_distribution.spa_cdn.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.spa_cdn.id
}

output "spa_url" {
  value = "https://${var.spa_subdomain}"
}

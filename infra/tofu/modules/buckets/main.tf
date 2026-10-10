# Object storage (S3-compatible, providers from GD3):
#   data bucket   versioned; telemetry/, symbols/ (private), releases/, shares/, tiles/ (public through the CDN)
#   backup bucket at a second provider; wal-g writes encrypted WAL and nightly
#                 base backups; old objects expire after the retention period
# Each role gets its own access key, made by hand in the provider's console
# (api + worker: read/write on the data bucket; postgres: write on the backup bucket).

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.data, aws.backup]
    }
  }
}

variable "data_bucket" {
  type = string
}

variable "backup_bucket" {
  type = string
}

variable "backup_retention_days" {
  type = number
}

resource "aws_s3_bucket" "data" {
  provider = aws.data
  bucket   = var.data_bucket
}

resource "aws_s3_bucket_versioning" "data" {
  provider = aws.data
  bucket   = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  provider   = aws.data
  bucket     = aws_s3_bucket.data.id
  depends_on = [aws_s3_bucket_versioning.data]

  # Deleted or replaced objects stay recoverable for 30 days, then go
  # (the API's retention and deletion jobs still reach them in time).
  rule {
    id     = "old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }
}

resource "aws_s3_bucket" "backup" {
  provider = aws.backup
  bucket   = var.backup_bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  provider = aws.backup
  bucket   = aws_s3_bucket.backup.id

  # wal-g deletes what it no longer needs; this is the safety net.
  rule {
    id     = "expire"
    status = "Enabled"
    filter {}
    expiration {
      days = var.backup_retention_days + 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }
}

# --- PF6: public tiles behind the CDN ------------------------------------------------------
# Tiles (tiles/<sha256>.jpg) are public by hash: the CDN hostname (dns module,
# cdn_target) serves them from this bucket, and viewers on any origin fetch them
# (WebGL refuses cross-origin textures without CORS). Every other prefix stays
# private and is reached through presigned URLs only.

variable "public_prefixes" {
  description = "Prefixes of the data bucket anyone may read (through the CDN)."
  type        = list(string)
  default     = ["tiles/"]
}

resource "aws_s3_bucket_cors_configuration" "data" {
  provider = aws.data
  bucket   = aws_s3_bucket.data.id

  cors_rule {
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    max_age_seconds = 86400
  }
}

resource "aws_s3_bucket_policy" "public_read" {
  count    = length(var.public_prefixes) > 0 ? 1 : 0
  provider = aws.data
  bucket   = aws_s3_bucket.data.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadByHash"
      Effect    = "Allow"
      Principal = "*"
      Action    = ["s3:GetObject"]
      Resource  = [for p in var.public_prefixes : "arn:aws:s3:::${var.data_bucket}/${p}*"]
    }]
  })
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}

output "backup_bucket" {
  value = aws_s3_bucket.backup.bucket
}

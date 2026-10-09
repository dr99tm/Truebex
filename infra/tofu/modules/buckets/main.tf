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

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}

output "backup_bucket" {
  value = aws_s3_bucket.backup.bucket
}

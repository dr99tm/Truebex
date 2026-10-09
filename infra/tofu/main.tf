# The Truebex API host and everything around it (PF14):
#   module.vm         the Linux VM, its firewall (443 from Cloudflare only, SSH by key)
#   module.buckets    the versioned data bucket and the backup bucket at a second provider
#   module.dns        api, api-staging, share, the CDN hostname, mail records; origin certificate
#   module.monitoring uptime checks of /health and /health/deep, the host heartbeat
#
#   cd infra/tofu
#   tofu init
#   tofu plan -var-file=terraform.tfvars
#   tofu apply -var-file=terraform.tfvars

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "hcloud" {
  token = var.hcloud_token
}

# The data bucket's provider (S3-compatible API).
provider "aws" {
  alias                       = "data"
  region                      = var.data_s3_region
  access_key                  = var.data_s3_access_key
  secret_key                  = var.data_s3_secret_key
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  s3_use_path_style           = true
  endpoints {
    s3 = var.data_s3_endpoint
  }
}

# The backup bucket's provider: a different company from the VM's.
provider "aws" {
  alias                       = "backup"
  region                      = var.backup_s3_region
  access_key                  = var.backup_s3_access_key
  secret_key                  = var.backup_s3_secret_key
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  s3_use_path_style           = true
  endpoints {
    s3 = var.backup_s3_endpoint
  }
}

provider "betteruptime" {
  api_token = var.betteruptime_api_token
}

data "cloudflare_ip_ranges" "cloudflare" {}

data "cloudflare_zone" "main" {
  name = var.zone_name
}

module "vm" {
  source            = "./modules/vm"
  name              = "truebex-api"
  server_type       = var.server_type
  location          = var.location
  image             = var.image
  ssh_public_key    = var.ssh_public_key
  ssh_allowed_cidrs = var.ssh_allowed_cidrs
  cloudflare_ranges = concat(data.cloudflare_ip_ranges.cloudflare.ipv4_cidr_blocks, data.cloudflare_ip_ranges.cloudflare.ipv6_cidr_blocks)
  user_data = templatefile("${path.module}/../host/cloud-init.yaml", {
    ssh_public_key    = var.ssh_public_key
    cloudflare_ranges = concat(data.cloudflare_ip_ranges.cloudflare.ipv4_cidr_blocks, data.cloudflare_ip_ranges.cloudflare.ipv6_cidr_blocks)
  })
}

module "buckets" {
  source = "./modules/buckets"
  providers = {
    aws.data   = aws.data
    aws.backup = aws.backup
  }
  data_bucket           = var.data_bucket
  backup_bucket         = var.backup_bucket
  backup_retention_days = var.backup_retention_days
}

module "dns" {
  source              = "./modules/dns"
  zone_id             = data.cloudflare_zone.main.id
  zone_name           = var.zone_name
  vm_ipv4             = module.vm.ipv4
  vm_ipv6             = module.vm.ipv6
  api_target          = var.api_target
  tunnel_cname        = var.tunnel_cname
  share_target        = var.share_target
  cdn_hostname        = var.cdn_hostname
  cdn_target          = var.cdn_target
  manage_mail_records = var.manage_mail_records
  spf_value           = var.spf_value
  dkim_records        = var.dkim_records
  dmarc_value         = var.dmarc_value
}

module "monitoring" {
  source      = "./modules/monitoring"
  api_base    = "https://api.${var.zone_name}"
  alert_email = var.alert_email
}

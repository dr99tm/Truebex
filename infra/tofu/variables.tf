# Values marked "from GD3" are placeholders until guides/GD3 (cloud cost and
# infrastructure) fixes the provider, size, region and retention.

variable "state_passphrase" {
  description = "Encrypts the local state and plans (at least 16 characters). Keep it with the age key."
  type        = string
  sensitive   = true
}

# --- Cloudflare ------------------------------------------------------------------

variable "cloudflare_api_token" {
  description = "Token with Zone:DNS:Edit, Zone:SSL and Certificates:Edit on truebex.com."
  type        = string
  sensitive   = true
}

variable "zone_name" {
  type    = string
  default = "truebex.com"
}

variable "api_target" {
  description = "Where api.truebex.com points: \"tunnel\" (the home PC, before the cutover) or \"vm\" (after it, infra/CUTOVER.md step 4)."
  type        = string
  default     = "tunnel"
  validation {
    condition     = contains(["tunnel", "vm"], var.api_target)
    error_message = "api_target is \"tunnel\" or \"vm\"."
  }
}

variable "tunnel_cname" {
  description = "The tunnel's hostname (<tunnel id>.cfargotunnel.com), kept only while api_target = \"tunnel\"."
  type        = string
  default     = ""
}

variable "share_target" {
  description = "CNAME target of share.truebex.com for PF5's share pages; empty = no record yet."
  type        = string
  default     = ""
}

variable "cdn_hostname" {
  description = "The CDN hostname in front of the public prefixes (tiles/, shares/, releases/), PF6."
  type        = string
  default     = "cdn"
}

variable "cdn_target" {
  description = "CNAME target of the CDN hostname (the data bucket's public endpoint); empty = no record yet."
  type        = string
  default     = ""
}

variable "manage_mail_records" {
  description = "Manage SPF, DKIM and DMARC here. Import the zone's existing records first (infra/README.md): a second SPF record breaks mail."
  type        = bool
  default     = false
}

variable "spf_value" {
  description = "The whole SPF record, every sender included, e.g. \"v=spf1 include:_spf.google.com include:<mail provider> ~all\"."
  type        = string
  default     = ""
}

variable "dkim_records" {
  description = "DKIM records from the mail provider."
  type = list(object({
    name  = string
    type  = string
    value = string
  }))
  default = []
}

variable "dmarc_value" {
  type    = string
  default = "v=DMARC1; p=quarantine; rua=mailto:hello@truebex.com; adkim=s; aspf=s"
}

# --- The VM (from GD3) ---------------------------------------------------------------

variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "server_type" {
  description = "4 vCPU / 8 GB / 160 GB SSD (from GD3)."
  type        = string
  default     = "cpx31"
}

variable "location" {
  description = "EU region (from GD3; the provider has no UK region)."
  type        = string
  default     = "nbg1"
}

variable "image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "ssh_public_key" {
  description = "The owner's SSH public key (ed25519)."
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "Where SSH may come from. Narrow it to the owner's address when it is stable."
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

# --- Object storage (from GD3) ------------------------------------------------------

variable "data_s3_endpoint" {
  description = "S3 endpoint of the data bucket (the API's STORAGE_BACKEND=s3), e.g. https://fsn1.your-objectstorage.com."
  type        = string
}

variable "data_s3_region" {
  type    = string
  default = "fsn1"
}

variable "data_bucket" {
  type    = string
  default = "truebex-data"
}

variable "data_s3_access_key" {
  description = "An admin key for creating the bucket (the API gets its own, narrower key)."
  type        = string
  sensitive   = true
}

variable "data_s3_secret_key" {
  type      = string
  sensitive = true
}

variable "backup_s3_endpoint" {
  description = "S3 endpoint at a SECOND provider for the Postgres backups, e.g. https://s3.eu-central-003.backblazeb2.com."
  type        = string
}

variable "backup_s3_region" {
  type    = string
  default = "eu-central-003"
}

variable "backup_bucket" {
  type    = string
  default = "truebex-db-backups"
}

variable "backup_s3_access_key" {
  type      = string
  sensitive = true
}

variable "backup_s3_secret_key" {
  type      = string
  sensitive = true
}

variable "backup_retention_days" {
  description = "Backups are kept this long (from GD3); wal-g keeps 30 nightly bases."
  type        = number
  default     = 30
}

# --- Monitoring ------------------------------------------------------------------------

variable "betteruptime_api_token" {
  type      = string
  sensitive = true
}

variable "alert_email" {
  description = "Uptime alerts go here and, by the monitor's app, to the owner's phone."
  type        = string
  default     = "hello@truebex.com"
}

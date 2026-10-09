# Cloudflare DNS for truebex.com (proxied, so a change is immediate) and the
# origin certificate Caddy presents ("Full (strict)").
#
# Before the cutover api.truebex.com is the tunnel's CNAME; set
# api_target = "vm" in CUTOVER.md step 4 to point it at the VM. Existing
# records must be imported before tofu manages them (infra/README.md).

terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
    tls = {
      source = "hashicorp/tls"
    }
  }
}

variable "zone_id" {
  type = string
}

variable "zone_name" {
  type = string
}

variable "vm_ipv4" {
  type = string
}

variable "vm_ipv6" {
  type = string
}

variable "api_target" {
  type = string
}

variable "tunnel_cname" {
  type = string
}

variable "share_target" {
  type = string
}

variable "cdn_hostname" {
  type = string
}

variable "cdn_target" {
  type = string
}

variable "manage_mail_records" {
  type = bool
}

variable "spf_value" {
  type = string
}

variable "dkim_records" {
  type = list(object({
    name  = string
    type  = string
    value = string
  }))
}

variable "dmarc_value" {
  type = string
}

# --- the API --------------------------------------------------------------------------

resource "cloudflare_record" "api_vm_a" {
  count   = var.api_target == "vm" ? 1 : 0
  zone_id = var.zone_id
  name    = "api"
  type    = "A"
  content = var.vm_ipv4
  proxied = true
  comment = "PF14: the API VM"
}

resource "cloudflare_record" "api_vm_aaaa" {
  count   = var.api_target == "vm" ? 1 : 0
  zone_id = var.zone_id
  name    = "api"
  type    = "AAAA"
  content = var.vm_ipv6
  proxied = true
  comment = "PF14: the API VM"
}

resource "cloudflare_record" "api_tunnel" {
  count   = var.api_target == "tunnel" && var.tunnel_cname != "" ? 1 : 0
  zone_id = var.zone_id
  name    = "api"
  type    = "CNAME"
  content = var.tunnel_cname
  proxied = true
  comment = "The home PC's tunnel; removed at the cutover"
}

# The new stack, reachable before and after the cutover.
resource "cloudflare_record" "api_staging" {
  zone_id = var.zone_id
  name    = "api-staging"
  type    = "A"
  content = var.vm_ipv4
  proxied = true
  comment = "PF14: the API VM (staging hostname)"
}

# --- share pages (PF5) and the CDN for tiles, shares and releases (PF6) ----------------

resource "cloudflare_record" "share" {
  count   = var.share_target != "" ? 1 : 0
  zone_id = var.zone_id
  name    = "share"
  type    = "CNAME"
  content = var.share_target
  proxied = true
}

resource "cloudflare_record" "cdn" {
  count   = var.cdn_target != "" ? 1 : 0
  zone_id = var.zone_id
  name    = var.cdn_hostname
  type    = "CNAME"
  content = var.cdn_target
  proxied = true
}

# --- mail (the smtp adapter's provider) ---------------------------------------------------

resource "cloudflare_record" "spf" {
  count   = var.manage_mail_records && var.spf_value != "" ? 1 : 0
  zone_id = var.zone_id
  name    = "@"
  type    = "TXT"
  content = var.spf_value
}

resource "cloudflare_record" "dkim" {
  for_each = var.manage_mail_records ? { for r in var.dkim_records : r.name => r } : {}
  zone_id  = var.zone_id
  name     = each.value.name
  type     = each.value.type
  content  = each.value.value
  proxied  = false
}

resource "cloudflare_record" "dmarc" {
  count   = var.manage_mail_records ? 1 : 0
  zone_id = var.zone_id
  name    = "_dmarc"
  type    = "TXT"
  content = var.dmarc_value
}

# --- the origin certificate (15 years, trusted by Cloudflare only) ------------------------

resource "tls_private_key" "origin" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_cert_request" "origin" {
  private_key_pem = tls_private_key.origin.private_key_pem
  subject {
    common_name  = "api.${var.zone_name}"
    organization = "Truebex"
  }
}

resource "cloudflare_origin_ca_certificate" "origin" {
  csr                = tls_cert_request.origin.cert_request_pem
  hostnames          = ["api.${var.zone_name}", "api-staging.${var.zone_name}"]
  request_type       = "origin-ecc"
  requested_validity = 5475
}

output "origin_certificate" {
  value = cloudflare_origin_ca_certificate.origin.certificate
}

output "origin_private_key" {
  value     = tls_private_key.origin.private_key_pem
  sensitive = true
}

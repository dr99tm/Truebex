# One Linux VM with the provider's firewall in front: 443 from Cloudflare's
# ranges only (Docker-published ports bypass the host's ufw, so this is the
# control that matters), 22 for SSH by key. Size and location from GD3.

terraform {
  required_providers {
    hcloud = {
      source = "hetznercloud/hcloud"
    }
  }
}

variable "name" {
  type = string
}

variable "server_type" {
  type = string
}

variable "location" {
  type = string
}

variable "image" {
  type = string
}

variable "ssh_public_key" {
  type = string
}

variable "ssh_allowed_cidrs" {
  type = list(string)
}

variable "cloudflare_ranges" {
  type = list(string)
}

variable "user_data" {
  type = string
}

resource "hcloud_ssh_key" "owner" {
  name       = "${var.name}-owner"
  public_key = var.ssh_public_key
}

resource "hcloud_firewall" "api" {
  name = "${var.name}-firewall"

  rule {
    description = "HTTPS from Cloudflare only"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = var.cloudflare_ranges
  }

  rule {
    description = "SSH (key only, see cloud-init)"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "ICMP"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "api" {
  name         = var.name
  server_type  = var.server_type
  location     = var.location
  image        = var.image
  ssh_keys     = [hcloud_ssh_key.owner.id]
  firewall_ids = [hcloud_firewall.api.id]
  user_data    = var.user_data
  backups      = false # the database has its own point-in-time backups; the host is rebuilt from infra/

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  lifecycle {
    # A changed cloud-init must not rebuild the running host; rebuild on purpose.
    ignore_changes = [user_data, image]
  }
}

output "ipv4" {
  value = hcloud_server.api.ipv4_address
}

output "ipv6" {
  value = hcloud_server.api.ipv6_address
}

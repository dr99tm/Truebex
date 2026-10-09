# OpenTofu (MPL-2.0) for the Truebex API host (PF14). State stays on the
# owner's PC, encrypted with a passphrase only the owner holds
# (TF_VAR_state_passphrase); no hosted state service.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.52"
    }
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    betteruptime = {
      source  = "BetterStackHQ/better-uptime"
      version = "~> 0.20"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  encryption {
    key_provider "pbkdf2" "owner" {
      passphrase = var.state_passphrase
    }
    method "aes_gcm" "owner" {
      keys = key_provider.pbkdf2.owner
    }
    state {
      method   = method.aes_gcm.owner
      enforced = true
    }
    plan {
      method   = method.aes_gcm.owner
      enforced = true
    }
  }
}

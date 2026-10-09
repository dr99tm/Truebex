output "vm_ipv4" {
  value = module.vm.ipv4
}

output "vm_ipv6" {
  value = module.vm.ipv6
}

output "ssh" {
  value = "ssh truebex@${module.vm.ipv4}"
}

output "data_bucket" {
  value = module.buckets.data_bucket
}

output "backup_bucket" {
  value = module.buckets.backup_bucket
}

# Copy both into infra/secrets/origin.sops.env with `sops` (infra/secrets/README.md).
output "origin_certificate" {
  value     = module.dns.origin_certificate
  sensitive = true
}

output "origin_private_key" {
  value     = module.dns.origin_private_key
  sensitive = true
}

output "host_heartbeat_url" {
  description = "HEARTBEAT_URL for /opt/truebex/secrets/host.env."
  value       = module.monitoring.heartbeat_url
  sensitive   = true
}

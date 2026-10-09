# External uptime checks (hosted, multi-region, every 60 s; provider from GD3)
# and the host's dead man's switch. Alerts by e-mail and the monitor's phone
# app (push); the owner's phone must have the app signed in.

terraform {
  required_providers {
    betteruptime = {
      source = "BetterStackHQ/better-uptime"
    }
  }
}

variable "api_base" {
  type = string
}

variable "alert_email" {
  type = string
}

resource "betteruptime_monitor" "health" {
  url                 = "${var.api_base}/health"
  monitor_type        = "status"
  check_frequency     = 60
  regions             = ["us", "eu", "as", "au"]
  email               = true
  push                = true
  call                = false
  sms                 = false
  recovery_period     = 180
  confirmation_period = 30
  pronounceable_name  = "Truebex API liveness"
}

resource "betteruptime_monitor" "health_deep" {
  url                   = "${var.api_base}/health/deep"
  monitor_type          = "expected_status_code"
  expected_status_codes = [200]
  check_frequency       = 60
  regions               = ["us", "eu", "as", "au"]
  email                 = true
  push                  = true
  call                  = false
  sms                   = false
  recovery_period       = 180
  confirmation_period   = 60
  pronounceable_name    = "Truebex API database, storage and worker"
}

# infra/host/bin/host-check.sh pings this every minute while the host is
# healthy; no ping for 5 minutes alerts (the host or its checks are down).
resource "betteruptime_heartbeat" "host" {
  name   = "Truebex API host checks"
  period = 60
  grace  = 240
  email  = true
  push   = true
  call   = false
  sms    = false
}

output "heartbeat_url" {
  value = betteruptime_heartbeat.host.url
}

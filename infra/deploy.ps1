<#
.SYNOPSIS
    Deploy the Truebex API to its VM (PF14). Run by the owner, never by a task.

.DESCRIPTION
    1. Packs server/ and infra/host/ from the committed HEAD (git archive).
    2. Decrypts infra/secrets/*.sops.env with sops (age key on this PC) into a temp folder.
    3. Writes caddy.env (Cloudflare's current ranges, the API hostnames) and .env (API_IMAGE).
    4. Copies everything to the VM over SSH, installs the Compose files, scripts, secrets (0600)
       and systemd timers into /opt/truebex.
    5. Builds server/Dockerfile (on the VM by default; -BuildLocally with Docker on this PC),
       pushes it when -Registry is set, then `docker compose pull` and `up -d`.
    6. Waits until /health/deep answers 200 with a fresh worker heartbeat.
    The decrypted secrets are deleted from this PC whatever happens.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File infra\deploy.ps1 -VmHost truebex@203.0.113.10
.EXAMPLE
    infra\deploy.ps1 -VmHost truebex@203.0.113.10 -HealthUrl https://api-staging.truebex.com/health/deep
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$VmHost,
    [string]$Registry = $env:TRUEBEX_REGISTRY,
    [string]$HealthUrl = 'https://api.truebex.com/health/deep',
    [string]$ApiHosts = 'api.truebex.com, api-staging.truebex.com',
    [switch]$BuildLocally,
    [switch]$AllowDirty
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot -Parent
$Infra = $PSScriptRoot

function Need($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is not on PATH (see infra/README.md, Prerequisites)" }
}
Need git; Need ssh; Need scp; Need sops
if ($BuildLocally) { Need docker }

if (-not $AllowDirty) {
    $dirty = git -C $Repo status --porcelain -- server infra
    if ($dirty) { throw "server/ or infra/ has uncommitted changes; commit them or pass -AllowDirty`n$dirty" }
}
$sha = (git -C $Repo rev-parse --short=12 HEAD).Trim()
$image = if ($Registry) { "$Registry/truebex-api:$sha" } else { "truebex-api:$sha" }
Write-Host "deploying $sha as $image to $VmHost"

$tmp = Join-Path ([IO.Path]::GetTempPath()) "truebex-deploy-$sha"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force (Join-Path $tmp 'secrets') | Out-Null
try {
    # 1. The release, exactly as committed (LF line endings, whatever this checkout uses).
    git -C $Repo -c core.autocrlf=false archive --format=tar -o (Join-Path $tmp 'release.tar') HEAD server infra/host
    if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }

    # 2. Secrets.
    foreach ($name in 'server', 'postgres', 'host') {
        $src = Join-Path $Infra "secrets\$name.sops.env"
        if (-not (Test-Path $src)) { throw "missing $src (infra/secrets/README.md)" }
        & sops --decrypt --output (Join-Path $tmp "secrets\$name.env") $src
        if ($LASTEXITCODE -ne 0) { throw "sops could not decrypt $src" }
    }
    foreach ($name in 'origin.pem', 'origin.key') {
        $src = Join-Path $Infra "secrets\$name.sops.env"
        & sops --decrypt --input-type binary --output-type binary --output (Join-Path $tmp "secrets\$name") $src
        if ($LASTEXITCODE -ne 0) { throw "sops could not decrypt $src" }
    }

    # 3. Cloudflare's ranges for Caddy's trusted proxies, and the image tag.
    $v4 = (Invoke-RestMethod 'https://www.cloudflare.com/ips-v4') -split "\s+" | Where-Object { $_ }
    $v6 = (Invoke-RestMethod 'https://www.cloudflare.com/ips-v6') -split "\s+" | Where-Object { $_ }
    $ranges = ($v4 + $v6) -join ' '
    $lf = "`n"
    [IO.File]::WriteAllText((Join-Path $tmp 'caddy.env'), "API_HOSTS=$ApiHosts${lf}CF_TRUSTED_PROXIES=$ranges$lf")
    [IO.File]::WriteAllText((Join-Path $tmp 'compose.env'), "API_IMAGE=$image$lf")

    # 5a. Optional local build.
    if ($BuildLocally) {
        docker build -t $image (Join-Path $Repo 'server')
        if ($LASTEXITCODE -ne 0) { throw 'docker build failed' }
        if ($Registry) { docker push $image; if ($LASTEXITCODE -ne 0) { throw 'docker push failed' } }
    }

    # 4. Copy and install (the install script travels as a file with LF endings).
    $build = if ($BuildLocally) { 'true' } else { 'false' }
    $remote = @"
set -eu
cd /tmp/truebex-deploy
tar -xf release.tar
install -d -m 0755 /opt/truebex /opt/truebex/bin /opt/truebex/postgres
install -d -m 0700 /opt/truebex/secrets
install -m 0644 infra/host/compose.yaml infra/host/Caddyfile /opt/truebex/
install -m 0644 infra/host/postgres/Dockerfile infra/host/postgres/restore-into.sh /opt/truebex/postgres/
install -m 0755 infra/host/bin/*.sh /opt/truebex/bin/
install -m 0600 secrets/* /opt/truebex/secrets/
install -m 0600 caddy.env /opt/truebex/caddy.env
install -m 0600 compose.env /opt/truebex/.env
sudo install -m 0644 infra/host/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now truebex-backup.timer truebex-restore-test.timer truebex-host-check.timer truebex-monthly-reboot.timer
if [ "$build" = false ]; then
  docker build -t '$image' server
  if [ -n '$Registry' ]; then docker push '$image'; fi
fi
cd /opt/truebex
if [ -n '$Registry' ]; then docker compose pull api worker; fi
docker compose build postgres
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
rm -rf /tmp/truebex-deploy

"@
    [IO.File]::WriteAllText((Join-Path $tmp 'install.sh'), ($remote -replace "`r", ''))

    ssh $VmHost 'rm -rf /tmp/truebex-deploy && mkdir -p /tmp/truebex-deploy && chmod 0700 /tmp/truebex-deploy'
    if ($LASTEXITCODE -ne 0) { throw "ssh to $VmHost failed" }
    scp -q -r "$tmp\*" "${VmHost}:/tmp/truebex-deploy/"
    if ($LASTEXITCODE -ne 0) { throw 'scp failed' }
    ssh $VmHost 'bash /tmp/truebex-deploy/install.sh'
    if ($LASTEXITCODE -ne 0) { throw 'remote install failed (the previous containers keep running unless Compose replaced them)' }
}
finally {
    # The decrypted secrets never outlive the deploy, here or on the VM.
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    ssh $VmHost 'rm -rf /tmp/truebex-deploy'
}

# 6. Health.
Write-Host "waiting for $HealthUrl ..."
$deadline = (Get-Date).AddMinutes(4)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10
        if ($r.db -eq 'ok' -and $r.storage -eq 'ok' -and $null -ne $r.worker_heartbeat_s -and $r.worker_heartbeat_s -lt 60) {
            Write-Host "healthy: db $($r.db), storage $($r.storage), worker heartbeat $($r.worker_heartbeat_s) s"
            Write-Host "deployed $sha"
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 5
}
Write-Host "FAIL: $HealthUrl did not report healthy within 4 minutes. On the VM: cd /opt/truebex; docker compose ps; docker compose logs --tail 100 api worker"
exit 1

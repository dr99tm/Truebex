<#
.SYNOPSIS
    Run the backup restore test on the API host now (PF14). The same test runs
    weekly by itself (truebex-restore-test.timer).

.DESCRIPTION
    Restores the latest base backup plus the archived WAL into a scratch
    container on the VM, compares every table's row count with production and
    prints "restore OK" (exit 0) or the tables that differ (exit 1).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File infra\restore-test.ps1 -VmHost truebex@203.0.113.10
#>
[CmdletBinding()]
param([Parameter(Mandatory)] [string]$VmHost)
$ErrorActionPreference = 'Stop'
ssh $VmHost 'sudo /opt/truebex/bin/restore-test.sh'
$code = $LASTEXITCODE
if ($code -ne 0) { Write-Host "restore test FAILED ($code)" }
exit $code

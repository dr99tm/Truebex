<#
.SYNOPSIS
    Try it for the Truebex platform repo under Claude Autopilot: serve the task's built out/ folder.

.DESCRIPTION
    Port = 3100 + the task number (T7 -> 3107) so two tasks never collide. Builds first if out/ is missing.
    The API for sign-in is whatever .env.local points at (production by default); run server\run.bat
    separately for a local API on :8000 and rebuild with NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:8000 to use it.
#>
[CmdletBinding()]
param()
$Worktree = (Get-Location).Path
if ($env:AUTOPILOT_WORKTREE) { $Worktree = $env:AUTOPILOT_WORKTREE }
Set-Location $Worktree
$n = 0
if ($env:AUTOPILOT_TASK_ID -match '^T(\d+)$') { $n = [int]$Matches[1] }
$port = 3100 + $n
if (-not (Test-Path (Join-Path $Worktree 'out\index.html'))) { & npm run build }
Write-Host "serving $Worktree\out on http://127.0.0.1:$port/"
& py -3.12 -m http.server $port --directory (Join-Path $Worktree 'out')

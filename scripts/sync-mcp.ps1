<#
.SYNOPSIS
    Copy the MCP bridge and its tool schema from the app repository into the
    @truebex/mcp package and the website (PF12; agent-interface.md §2, §6.5, §9).

.DESCRIPTION
    Run at each app release. Copies, never edits:
      <AppRepo>\Tools\mcp\server.js                              -> packages\mcp\server.js
      <AppRepo>\Tools\mcp\tools.json                             -> packages\mcp\tools.json and src\content\tools.json
      <AppRepo>\Docs\roadmap\fixtures\contracts\agent\*.jsonl    -> packages\mcp\test\fixtures\
    Then run the package tests (server\tests\test_pf12_mcp_package.py) and the
    site build, and commit. A fix to the bridge goes to the app repository first.

.PARAMETER AppRepo
    The app repository (default T:\unreal5_7_4_projects\truebex_compact).
#>
[CmdletBinding()]
param([string]$AppRepo = 'T:\unreal5_7_4_projects\truebex_compact')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Mcp = Join-Path $AppRepo 'Tools\mcp'
$Server = Join-Path $Mcp 'server.js'
$Tools = Join-Path $Mcp 'tools.json'
if (-not (Test-Path $Server) -or -not (Test-Path $Tools)) {
    throw "No $Mcp\server.js and tools.json yet (AI1 ships them). The package keeps its current copies."
}
$null = Get-Content $Tools -Raw | ConvertFrom-Json  # refuse a broken file before copying anything
Copy-Item $Server (Join-Path $Root 'packages\mcp\server.js') -Force
Copy-Item $Tools (Join-Path $Root 'packages\mcp\tools.json') -Force
Copy-Item $Tools (Join-Path $Root 'src\content\tools.json') -Force
Write-Host "copied server.js and tools.json from $Mcp"

$Fixtures = Join-Path $AppRepo 'Docs\roadmap\fixtures\contracts\agent'
if (Test-Path $Fixtures) {
    $Out = Join-Path $Root 'packages\mcp\test\fixtures'
    Get-ChildItem $Out -Filter *.jsonl | Remove-Item -Force
    Get-ChildItem $Fixtures -Filter *.jsonl | Copy-Item -Destination $Out -Force
    Write-Host "copied the agent fixture scripts from $Fixtures"
} else {
    Write-Host "no $Fixtures yet: the package tests keep PF12's interim scripts"
}
Write-Host 'Next: server\.venv\Scripts\python.exe -m pytest -q server\tests\test_pf12_mcp_package.py, npm run build, commit.'

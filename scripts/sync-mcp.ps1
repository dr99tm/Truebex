<#
.SYNOPSIS
    Copy the MCP bridge AI1 ships from the app repository into the @truebex/mcp
    package and the website (PF12, PF12b; agent-interface.md §2, §6.5, §6.6, §9).

.DESCRIPTION
    Run after an app release changes the app's Tools\mcp\. Copies, never edits:
      <AppRepo>\Tools\mcp\truebex-mcp.mjs                       -> packages\mcp\truebex-mcp.mjs
      <AppRepo>\Tools\mcp\lib\*.mjs                             -> packages\mcp\lib\
      <AppRepo>\Tools\mcp\tools.json                            -> packages\mcp\tools.json and src\content\tools.json
      <AppRepo>\Tools\mcp\instructions.md                       -> packages\mcp\instructions.md
      <AppRepo>\Tools\mcp\test\*.mjs                            -> packages\mcp\test\  (the app's fake app and node tests)
      <AppRepo>\Docs\roadmap\fixtures\contracts\agent\*.jsonl   -> packages\mcp\test\fixtures\  (the wire scripts)
    lib\, test\ and test\fixtures\ are mirrored: a file the app no longer has is removed.
    Kept as they are: the package's own README.md (the npm install notes), LICENSE and
    package.json. Not copied: the app's README.md, manifest.json and truebex.mcpb (the
    MCP Bundle ships with the app, beside the installed bridge).

    Refuses, before copying anything: a missing file of that layout, a tools.json that
    does not parse, or one whose "schema" is not truebex-tools/1. A fix to the bridge goes
    to the app repository first, then this script. Then run the package tests
    (server\tests\test_pf12_mcp_package.py), npm run build, and commit.

.PARAMETER AppRepo
    The app repository (default T:\unreal5_7_4_projects\truebex_compact). Only read.

.PARAMETER Root
    The platform repository to copy into (default: the one holding this script).
#>
[CmdletBinding()]
param(
    [string]$AppRepo = 'T:\unreal5_7_4_projects\truebex_compact',
    [string]$Root = ''
)
$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }  # PowerShell 5.1 has no $PSScriptRoot in param defaults
$Schema = 'truebex-tools/1'

function Refuse([string]$why) {
    [Console]::Error.WriteLine("sync-mcp: $why. Nothing was copied.")
    exit 1
}

foreach ($dir in $AppRepo, $Root) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { Refuse "no folder $dir" }
}
$AppRepo = (Resolve-Path -LiteralPath $AppRepo).ProviderPath.TrimEnd('\')
$Root = (Resolve-Path -LiteralPath $Root).ProviderPath.TrimEnd('\')
$Mcp = Join-Path $AppRepo 'Tools\mcp'
$Fixtures = Join-Path $AppRepo 'Docs\roadmap\fixtures\contracts\agent'
$Pkg = Join-Path $Root 'packages\mcp'
$SiteTools = Join-Path $Root 'src\content\tools.json'

# --- check the whole layout first ------------------------------------------------------------
foreach ($name in 'truebex-mcp.mjs', 'tools.json', 'instructions.md', 'test\fake-app.mjs', 'test\helpers.mjs') {
    if (-not (Test-Path -LiteralPath (Join-Path $Mcp $name) -PathType Leaf)) { Refuse "no $Mcp\$name" }
}
$Lib = @(Get-ChildItem -LiteralPath (Join-Path $Mcp 'lib') -Filter *.mjs -File -ErrorAction SilentlyContinue)
if ($Lib.Count -eq 0) { Refuse "no $Mcp\lib\*.mjs" }
$Tests = @(Get-ChildItem -LiteralPath (Join-Path $Mcp 'test') -Filter *.mjs -File)
$Scripts = @(Get-ChildItem -LiteralPath $Fixtures -Filter *.jsonl -File -ErrorAction SilentlyContinue)
if ($Scripts.Count -eq 0) { Refuse "no wire fixture scripts in $Fixtures" }
if (-not (Test-Path -LiteralPath $Pkg -PathType Container)) { Refuse "no package folder $Pkg" }

$ToolsFile = Join-Path $Mcp 'tools.json'
$text = [System.IO.File]::ReadAllText($ToolsFile, [System.Text.Encoding]::UTF8)
try {
    $doc = $text | ConvertFrom-Json
} catch {
    Refuse "$ToolsFile does not parse as JSON ($($_.Exception.Message))"
}
if ($null -eq $doc -or $doc.schema -ne $Schema) { Refuse "$ToolsFile has schema '$($doc.schema)', not $Schema" }
if (@($doc.tools).Count -eq 0) { Refuse "$ToolsFile lists no tools" }

# --- copy -------------------------------------------------------------------------------------
function Copy-One([string]$from, [string]$to) {
    $dir = Split-Path -Parent $to
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Copy-Item -LiteralPath $from -Destination $to -Force
    $bytes = (Get-Item -LiteralPath $to).Length
    Write-Host ("copied {0} -> {1} ({2} bytes)" -f $from.Substring($AppRepo.Length).TrimStart('\'), $to.Substring($Root.Length).TrimStart('\'), $bytes)
}

function Mirror([System.IO.FileInfo[]]$files, [string]$into, [string]$filter) {
    if (-not (Test-Path -LiteralPath $into)) { New-Item -ItemType Directory -Path $into -Force | Out-Null }
    $keep = @($files | ForEach-Object { $_.Name })
    foreach ($old in @(Get-ChildItem -LiteralPath $into -Filter $filter -File)) {
        if ($keep -notcontains $old.Name) {
            Remove-Item -LiteralPath $old.FullName -Force
            Write-Host ("removed {0} (not in the landed layout)" -f $old.FullName.Substring($Root.Length).TrimStart('\'))
        }
    }
    foreach ($f in $files) { Copy-One $f.FullName (Join-Path $into $f.Name) }
}

foreach ($name in 'truebex-mcp.mjs', 'tools.json', 'instructions.md') {
    Copy-One (Join-Path $Mcp $name) (Join-Path $Pkg $name)
}
Copy-One $ToolsFile $SiteTools
Mirror $Lib (Join-Path $Pkg 'lib') '*.mjs'
Mirror $Tests (Join-Path $Pkg 'test') '*.mjs'
Mirror $Scripts (Join-Path $Pkg 'test\fixtures') '*.jsonl'

Write-Host ("tools.json {0}: {1} tools ({2})" -f $doc.version, @($doc.tools).Count, $Schema)
Write-Host 'Next: server\.venv\Scripts\python.exe -m pytest -q server\tests\test_pf12_mcp_package.py, npm run build, commit.'
exit 0

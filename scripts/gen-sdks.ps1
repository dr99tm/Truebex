<#
.SYNOPSIS
    Regenerate openapi/v1.json and the Python and JavaScript SDKs from it (PF12).

.DESCRIPTION
    1. server\scripts\export_openapi.py --v1        -> openapi/v1.json (the API's own description)
    2. datamodel-code-generator (MIT, pinned)       -> sdks/python/truebex/models.py (TypedDicts)
    3. openapi-typescript (MIT, pinned)             -> sdks/js/src/schema.d.ts
    4. sdks/generate.py                             -> the operation layer of both SDKs
    The generator tools live in .sdk-tools\ (git-ignored), made on first run.
    Commit what changed; server/tests/test_pf12_openapi_sdks.py fails on drift.
    Publishing (PyPI `truebex`, npm `@truebex/sdk`) is the owner's: see
    docs/roadmap/40/PF12-public-api-sdks-webhooks-and-the-mcp-package.md (As-built).
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = '1'

$DataModelCodegen = 'datamodel-code-generator==0.26.5'
$OpenApiTypescript = 'openapi-typescript@7.13.0'

function Run($what, [scriptblock]$body) {
    Write-Host "=== $what ==="
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$what failed ($LASTEXITCODE)" }
}

$ServerPy = Join-Path $Root 'server\.venv\Scripts\python.exe'
if (-not (Test-Path $ServerPy)) { throw 'server\.venv is missing: run scripts\autopilot-setup.ps1 (or make the venv) first' }
Run 'export openapi/v1.json' { & $ServerPy server\scripts\export_openapi.py --v1 }

$Tools = Join-Path $Root '.sdk-tools\venv'
$ToolsPy = Join-Path $Tools 'Scripts\python.exe'
if (-not (Test-Path $ToolsPy)) {
    Run 'make .sdk-tools venv' { & py -3.12 -m venv $Tools }
}
Run "install $DataModelCodegen" { & $ToolsPy -m pip install -q $DataModelCodegen }
Run 'python models' {
    & $ToolsPy -m datamodel_code_generator --input openapi/v1.json --input-file-type openapi `
        --output sdks/python/truebex/models.py --output-model-type typing.TypedDict `
        --target-python-version 3.11 --use-schema-description --use-field-description --disable-timestamp `
        --enum-field-as-literal all --use-standard-collections --use-union-operator --encoding utf-8
}
Run 'typescript schema' { & npx --yes $OpenApiTypescript openapi/v1.json -o sdks/js/src/schema.d.ts }
Run 'operations' { & $ServerPy sdks\generate.py }
Write-Host 'SDKs regenerated. Review and commit openapi/, sdks/.'

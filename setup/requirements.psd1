# What this repo needs on a machine. Read by setup\setup.ps1 (Windows); setup/setup.sh mirrors the Linux part.
# Tools: found on PATH (unless NoPath) or at Paths, version read with Command + Args and the first group of Pattern, then
# checked against Min (inclusive) and Below (exclusive). Missing ones install with winget (Winget, Version) or Install.
# Steps: run in Dir (default the repo root) for the selected components; Skip = a path that, when present, skips it.
# Files: things git doesn't carry. Template = a tracked file copied in when the file is absent.
@{
    Name       = 'Truebex platform'
    Components = @{
        core     = 'Site (Next.js) + API server (FastAPI) + their tests'
        postgres = 'PostgreSQL binaries for the postgres-marked tests and the whole suite on Postgres'
        sdk      = 'Regenerating the SDKs and mobile clients (scripts\gen-sdks.ps1, gen-clients.ps1)'
        mobile   = 'The Flutter Android app in mobile\'
        host     = 'Serving api.truebex.com from this machine (cloudflared tunnel)'
        infra    = 'infra\ deploys (OpenTofu, sops, age)'
        deploy   = 'Publishing truebex.com (the main-branch deploy checkout)'
    }
    Tools      = @(
        @{ Name = 'git'; Command = 'git'; Args = '--version'; Pattern = 'version (\d+\.\d+\.\d+)'; Min = '2.40'; Winget = 'Git.Git' }
        @{ Name = 'node'; Command = 'node'; Args = '--version'; Pattern = 'v(\d+\.\d+\.\d+)'; Min = '22.0'; Below = '26.0'
            Winget = 'OpenJS.NodeJS.LTS'; Version = '24.22.1'; Note = 'CI uses 22, the owner''s PC 24' }
        @{ Name = 'python'; Command = 'python'; Args = '--version'; Pattern = 'Python (\d+\.\d+\.\d+)'; Min = '3.12'; Below = '3.13'
            Paths = @('%LOCALAPPDATA%\Programs\Python\Python312\python.exe', '%ProgramFiles%\Python312\python.exe')
            Winget = 'Python.Python.3.12'; Scope = 'machine'; Note = 'pins don''t install on 3.13+' }
        @{ Name = 'msedge'; Command = 'msedge'; Paths = @('%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe', '%ProgramFiles%\Microsoft\Edge\Application\msedge.exe')
            Optional = $true; Winget = 'Microsoft.Edge'; Note = 'headless self-tests (CDP drivers)' }
        @{ Name = 'pg_ctl'; Component = 'postgres'; Command = 'pg_ctl'; Args = '--version'; Pattern = '(\d+\.\d+)'; Min = '16.0'
            Paths = @('%ProgramFiles%\PostgreSQL\*\bin\pg_ctl.exe'); Winget = 'PostgreSQL.PostgreSQL.17'
            Override = '--mode unattended --unattendedmodeui none --superpassword postgres --servicepassword postgres --enable-components server,commandlinetools'
            Note = 'tests run their own throwaway cluster with initdb; the service password is postgres' }
        @{ Name = 'java'; Component = 'sdk'; Command = 'java'; Args = '-version'; Pattern = 'version "(\d+[\d.]*)'; Min = '17.0'
            Paths = @('%JAVA_HOME%\bin\java.exe', '%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe', '%ProgramFiles%\Microsoft\jdk-17*\bin\java.exe')
            Winget = 'Microsoft.OpenJDK.17'; Note = 'openapi-generator 7.26 (gen-clients.ps1)' }
        @{ Name = 'java (mobile)'; Component = 'mobile'; Command = 'java'; Args = '-version'; Pattern = 'version "(\d+[\d.]*)'; Min = '17.0'
            Paths = @('%JAVA_HOME%\bin\java.exe', '%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe', '%ProgramFiles%\Microsoft\jdk-17*\bin\java.exe')
            Winget = 'Microsoft.OpenJDK.17' }
        @{ Name = 'flutter'; Component = 'mobile'; Command = 'flutter'; Args = '--version'; Pattern = 'Flutter (\d+\.\d+\.\d+)'; Min = '3.44.1'
            Paths = @('%USERPROFILE%\Development\flutter\bin\flutter.bat')
            Install = 'git clone --depth 1 --branch 3.44.1 https://github.com/flutter/flutter.git "$env:USERPROFILE\Development\flutter"; [Environment]::SetEnvironmentVariable(''Path'', [Environment]::GetEnvironmentVariable(''Path'',''User'') + '';'' + "$env:USERPROFILE\Development\flutter\bin", ''User'')'
            Note = 'mobile\.metadata pins 3.44.1 stable' }
        @{ Name = 'Android Studio'; Component = 'mobile'; Command = 'studio64'; Paths = @('%ProgramFiles%\Android\Android Studio\bin\studio64.exe')
            Winget = 'Google.AndroidStudio'; Note = 'then SDK platform 36, build-tools 36, NDK 27.0.12077973 and 28.2.13676358 in its SDK Manager' }
        @{ Name = 'cloudflared'; Component = 'host'; Command = 'cloudflared'; Args = '--version'; Pattern = 'version (\d+\.\d+\.\d+)'
            Paths = @('%USERPROFILE%\.cloudflared\cloudflared.exe', '%ProgramFiles(x86)%\cloudflared\cloudflared.exe'); Winget = 'Cloudflare.cloudflared' }
        @{ Name = 'tofu'; Component = 'infra'; Command = 'tofu'; Args = '--version'; Pattern = 'v(\d+\.\d+\.\d+)'; Min = '1.8'; Winget = 'OpenTofu.Tofu' }
        @{ Name = 'sops'; Component = 'infra'; Command = 'sops'; Args = '--version'; Pattern = '(\d+\.\d+\.\d+)'; Winget = 'SecretsOPerationS.SOPS' }
        @{ Name = 'age'; Component = 'infra'; Command = 'age'; Args = '--version'; Pattern = 'v?(\d+\.\d+\.\d+)'; Winget = 'FiloSottile.age' }
    )
    Steps      = @(
        @{ Name = 'npm ci'; Run = 'npm ci --no-audit --no-fund' }
        @{ Name = 'server venv'; Dir = 'server'; Skip = 'server\.venv\Scripts\python.exe'; Run = '& ''{tool:python}'' -m venv .venv' }
        @{ Name = 'server packages'; Dir = 'server'; Run = '.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r requirements-dev.txt' }
        @{ Name = 'flutter pub get'; Component = 'mobile'; Dir = 'mobile'; Run = 'flutter pub get' }
    )
    Files      = @(
        @{ Path = '.env.local'; Template = '.env.example'; Kind = 'config'
            Note = 'NEXT_PUBLIC_AUTH_URL / NEXT_PUBLIC_SHEETS_URL are baked into the build; production builds need the production values (not secrets)' }
        @{ Path = 'server\.env'; Template = 'server\.env.example'; Kind = 'config, holds secrets'
            Note = 'local API runs only; tests set their own env. Real keys come from the owner, never from git' }
        @{ Path = 'T:\unreal5_7_4_projects\truebex_compact'; Kind = 'sibling repo'
            Note = 'dr99tm/truebex-compact at this path: contract-fixture and taxonomy tests skip without it; scripts\sync-*.ps1 need it' }
        @{ Path = 'X:\Truebex_site_files\Truebex'; Component = 'deploy'; Required = $true; Kind = 'deploy checkout'
            Note = 'clone of the main branch; see .claude\skills\truebex-deploy' }
        @{ Path = '%USERPROFILE%\.cloudflared\config.yml'; Component = 'host'; Required = $true; Kind = 'secret'
            Note = 'tunnel config + credentials json + cert.pem; keep a copy in the password manager' }
        @{ Path = 'infra\secrets\api.sops.env'; Component = 'infra'; Kind = 'secret'
            Note = 'not created yet: infra\.sops.yaml still has the placeholder age recipient' }
    )
}

# Real email for the Truebex API on the owner's PC (api.truebex.com -> win-tunnel -> localhost:8001): Amazon SES over
# SMTP (the `smtp` mail adapter, server/app/mail/smtp.py, STARTTLS on 587) instead of the `console` stand-in, which
# only printed every mail - sign-in codes and password-reset links included - into the API log.
#
# Run it yourself, in your own terminal, signed in with `aws login` (it creates an IAM user and an access key, which
# needs your rights; nothing here can be run from a phone):
#   powershell -NoProfile -ExecutionPolicy Bypass -File X:\Truebex\infra\setup-api-mail.ps1
#   ... -To someone@example.com     where the test mail goes (default: ALERT_EMAIL, else SUPPORT_EMAIL, in server\.env)
#   ... -Rotate                     a new key even when one already works (the old one is deleted after the test)
#
# What it does:
#   1. IAM user `truebex-api-smtp` with one inline policy: ses:SendRawEmail on the truebex.com identity in eu-central-1,
#      only from @truebex.com addresses. Nothing else.
#   2. An access key for it, turned into the SES SMTP password (AWS's documented SigV4 derivation, version 4).
#   3. X:\Truebex\server\.env (git-ignored): MAIL_BACKEND=smtp, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD.
#   4. Restarts the "Truebex API (port 8001)" scheduled task and sends one test mail through SES.
# No secret is printed, written to any other file, or passed on a command line.

param(
    # Empty: the admin mailbox from server\.env (ALERT_EMAIL, else SUPPORT_EMAIL), so no address lives in this repo.
    [string]$To = '',
    [switch]$Rotate,
    [string]$Region = 'eu-central-1',
    [string]$Domain = 'truebex.com',
    [string]$EnvFile = 'X:\Truebex\server\.env',
    [string]$TaskName = 'Truebex API (port 8001)',
    [string]$UserName = 'truebex-api-smtp',
    # Only the read-only checks (who you are, SES, the domain, whether the user exists); changes nothing.
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
function Say([string]$m) { Write-Host "[api-mail] $m" }
if (-not $To -and (Test-Path $EnvFile)) {
    foreach ($name in 'ALERT_EMAIL', 'SUPPORT_EMAIL') {
        $line = Get-Content $EnvFile | Where-Object { $_ -match "^$name=\s*(\S+@\S+)\s*$" } | Select-Object -First 1
        if ($line -and $line -match '=\s*(\S+@\S+)') { $To = $Matches[1]; break }
    }
}
if (-not $To -and -not $CheckOnly) { throw "No test-mail address: pass -To, or set ALERT_EMAIL in $EnvFile" }
# Windows PowerShell 5.1 turns a native command's stderr into errors that 'Stop' would throw on: run them under
# 'Continue', judge by the exit code, and keep only standard output.
# The program itself (Get-Command -CommandType Application): a PowerShell function of the same name would win
# otherwise, since names ignore case and functions come first.
function Native([string]$exe, [object[]]$argv) {
    $program = Get-Command $exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $all = & $program.Source @argv 2>&1 } finally { $ErrorActionPreference = $prev }
    $script:NativeExit = $LASTEXITCODE
    [pscustomobject]@{ Out = @($all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] }); Err = @($all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" }) }
}
# One string (ConvertFrom-Json in 5.1 reads each piped line as its own document, so lines must be joined first).
function Invoke-AwsCli { $r = Native 'aws' $args; if ($script:NativeExit -ne 0) { throw "aws $($args[0]) $($args[1]) failed: $($r.Err -join ' ')" }; ($r.Out | ForEach-Object { "$_" }) -join "`n" }

if (-not (Test-Path $EnvFile)) { throw "The API's settings file $EnvFile does not exist." }
$account = (Invoke-AwsCli sts get-caller-identity --query Account --output text).Trim()
Say "AWS account $account, region $Region."
$ses = Invoke-AwsCli sesv2 get-account --region $Region --output json | ConvertFrom-Json
if (-not $ses.ProductionAccessEnabled -or -not $ses.SendingEnabled) { throw 'SES in this region is not in production or sending is off.' }
$identity = Invoke-AwsCli sesv2 get-email-identity --email-identity $Domain --region $Region --output json | ConvertFrom-Json
if (-not $identity.VerifiedForSendingStatus) { throw "SES does not have $Domain verified for sending in $Region." }
Say "SES ready: $Domain verified, production access, $($ses.SendQuota.Max24HourSend) mails a day."

# 1. The user and its one permission.
$null = Native 'aws' @('iam', 'get-user', '--user-name', $UserName)
if ($CheckOnly) {
    Say "Check only: IAM user $UserName $(if ($script:NativeExit -eq 0) { 'exists' } else { 'does not exist yet (or you cannot read IAM)' }). Nothing was changed."
    return
}
if ($script:NativeExit -ne 0) {
    Invoke-AwsCli iam create-user --user-name $UserName --tags 'Key=Project,Value=truebex-api' 'Key=Purpose,Value=api-mail-smtp' | Out-Null
    Say "IAM user $UserName created."
} else { Say "IAM user $UserName already exists." }
# SES also authorizes the configuration set a mail goes through: the domain's default set (truebex-default, which
# records the Desk's sending events) applies to every mail from it, so the permission names that set too.
$resources = @("arn:aws:ses:${Region}:${account}:identity/$Domain")
$configSet = "$($identity.ConfigurationSetName)".Trim()
if ($configSet) { $resources += "arn:aws:ses:${Region}:${account}:configuration-set/$configSet" }
$policy = @{
    Version   = '2012-10-17'
    Statement = @(@{
        Sid       = 'SendAsTruebex'
        Effect    = 'Allow'
        Action    = 'ses:SendRawEmail'
        Resource  = $resources
        Condition = @{ StringLike = @{ 'ses:FromAddress' = "*@$Domain" } }
    })
} | ConvertTo-Json -Depth 6
$policyFile = Join-Path $env:TEMP "truebex-api-ses-policy-$PID.json"
[IO.File]::WriteAllText($policyFile, $policy, (New-Object Text.UTF8Encoding($false)))
try { Invoke-AwsCli iam put-user-policy --user-name $UserName --policy-name truebex-api-ses-send --policy-document "file://$policyFile" | Out-Null }
finally { Remove-Item $policyFile -Force -ErrorAction SilentlyContinue }
Say "Permission set: ses:SendRawEmail from @$Domain only$(if ($configSet) { ", through the configuration set $configSet" })."

# 2. The key: kept when one already works and -Rotate is not given.
$lines = [IO.File]::ReadAllLines($EnvFile)
$currentUser = ($lines | Where-Object { $_ -match '^SMTP_USER=' } | Select-Object -First 1) -replace '^SMTP_USER=', ''
$keys = @((Invoke-AwsCli iam list-access-keys --user-name $UserName --output json | ConvertFrom-Json).AccessKeyMetadata)
$haveWorking = ($lines -match '^MAIL_BACKEND=smtp$').Count -gt 0 -and $currentUser -and ($keys.AccessKeyId -contains $currentUser)
if ($haveWorking -and -not $Rotate) {
    Say 'The API already sends with a key of this user; keeping it (use -Rotate for a new one).'
    $newKeyId = $null
} else {
    # At most 2 keys per user: drop any key that the API is not using before making a new one.
    foreach ($k in $keys) { if ($k.AccessKeyId -ne $currentUser) { Invoke-AwsCli iam delete-access-key --user-name $UserName --access-key-id $k.AccessKeyId | Out-Null } }
    $created = (Invoke-AwsCli iam create-access-key --user-name $UserName --output json | ConvertFrom-Json).AccessKey
    $newKeyId = $created.AccessKeyId
    # SES SMTP password = base64(0x04 || HMAC chain over the secret key), AWS's documented derivation.
    function Hmac([byte[]]$key, [string]$msg) { ([System.Security.Cryptography.HMACSHA256]::new($key)).ComputeHash([Text.Encoding]::UTF8.GetBytes($msg)) }
    $sig = Hmac ([Text.Encoding]::UTF8.GetBytes('AWS4' + $created.SecretAccessKey)) '11111111'
    foreach ($part in @($Region, 'ses', 'aws4_request', 'SendRawEmail')) { $sig = Hmac $sig $part }
    $smtpPassword = [Convert]::ToBase64String([byte[]](@([byte]4) + $sig))
    $created = $null

    # 3. The .env lines (replaced or added; every other line kept; UTF-8 without a BOM, which the API's reader needs).
    $want = [ordered]@{
        MAIL_BACKEND  = 'smtp'
        SMTP_HOST     = "email-smtp.$Region.amazonaws.com"
        SMTP_PORT     = '587'
        SMTP_USER     = $newKeyId
        SMTP_PASSWORD = $smtpPassword
    }
    $out = New-Object System.Collections.Generic.List[string]
    $done = @{}
    foreach ($line in $lines) {
        $name = ($line -split '=', 2)[0]
        if ($want.Contains($name)) { $out.Add("$name=$($want[$name])"); $done[$name] = $true } else { $out.Add($line) }
    }
    foreach ($name in $want.Keys) { if (-not $done[$name]) { $out.Add("$name=$($want[$name])") } }
    [IO.File]::WriteAllText($EnvFile, (($out -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding($false)))
    $smtpPassword = $null
    Say "Mail settings written to $EnvFile (MAIL_BACKEND=smtp through email-smtp.$Region.amazonaws.com)."
}

# 4. Restart the API so it reads them.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn app\.main:app .*--port 8001' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $TaskName
    Say "Restarted '$TaskName'."
} else { Say "No scheduled task '$TaskName': restart the API yourself so it reads the new settings." }

# The test mail, with the settings the API now reads (a new IAM key can take a minute to work for SMTP).
$py = 'X:\Truebex\server\.venv\Scripts\python.exe'
$test = @'
import os, smtplib, ssl, sys
sys.path.insert(0, os.getcwd())  # X:\Truebex\server: the API's package and its .env
from email.message import EmailMessage
from app.config import get_settings
s = get_settings()
m = EmailMessage()
m["From"] = s.mail_from
m["To"] = sys.argv[1]
m["Subject"] = "Truebex API mail test"
m.set_content("This is a test from the Truebex API. Sign-in codes and password-reset links now go out through Amazon SES.")
with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as c:
    c.starttls(context=ssl.create_default_context())
    c.login(s.smtp_user, s.smtp_password)
    c.send_message(m)
print("sent")
'@
$sent = $false
Push-Location 'X:\Truebex\server'
try {
    for ($i = 1; $i -le 6 -and -not $sent; $i++) {
        $testFile = Join-Path $env:TEMP "truebex-api-mail-test-$PID.py"
        [IO.File]::WriteAllText($testFile, $test, (New-Object Text.UTF8Encoding($false)))
        try { $r = Native $py @($testFile, $To) } finally { Remove-Item $testFile -Force -ErrorAction SilentlyContinue }
        if ($script:NativeExit -eq 0 -and ($r.Out -join '') -match 'sent') { $sent = $true }
        else {
            $why = @($r.Err + $r.Out) | Where-Object { "$_" -match 'Error|535|554|refused' } | Select-Object -Last 1
            Say "test $i/6 not sent yet ($("$why".Trim())); retrying in 15 s"
            Start-Sleep -Seconds 15
        }
    }
} finally { Pop-Location }
if (-not $sent) { throw 'The test mail could not be sent. The settings are written; check the SES console and run this again.' }
Say "Test mail sent to $To through SES."

# The old key, once the new one has proved itself.
if ($newKeyId) {
    foreach ($k in @((Invoke-AwsCli iam list-access-keys --user-name $UserName --output json | ConvertFrom-Json).AccessKeyMetadata)) {
        if ($k.AccessKeyId -ne $newKeyId) { Invoke-AwsCli iam delete-access-key --user-name $UserName --access-key-id $k.AccessKeyId | Out-Null; Say 'Old key deleted.' }
    }
}
Say 'Done. The API now emails sign-in codes and password-reset links.'

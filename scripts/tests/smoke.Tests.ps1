$ErrorActionPreference = 'Stop'
$script:SmokePath = Join-Path $PSScriptRoot '../smoke.ps1'
$global:HysSmokeMockPublished = $false
$global:HysSmokeMockPrivateChecks = 0
$global:HysSmokeMockMigrationExit = 0
$global:HysSmokeMockMissingService = $false
$global:HysSmokeMockBadHealth = $false

function Invoke-RestMethod {
    param($Uri, [switch]$UseBasicParsing, [switch]$SkipCertificateCheck, $TimeoutSec, $MaximumRedirection)
    if ($global:HysSmokeMockBadHealth) { return @{status='failed'} }
    if ($Uri -match '/ready$') { return @{status='ready'} }
    return @{status='ok'}
}
function Invoke-WebRequest {
    param($Uri, [switch]$UseBasicParsing, [switch]$SkipCertificateCheck, $TimeoutSec, $MaximumRedirection)
    return @{Content=('DATOS 100 % SINT' + [char]0xC9 + 'TICOS')}
}
function docker {
    $global:LASTEXITCODE = 0
    $command = $args -join ' '
    if ($command -match 'ps -a --format json migrate') { return ('{"State":"exited","ExitCode":' + $global:HysSmokeMockMigrationExit + '}') }
    if ($command -match 'ps --status exited --services migrate') { return 'migrate' }
    if ($command -match 'ps -q') {
        if ($global:HysSmokeMockMissingService) { return '' }
        return 'synthetic-container'
    }
    if ($command -match '^port ') {
        $global:LASTEXITCODE = 1
        return ''
    }
    if ($command -match '^inspect ') {
        $global:HysSmokeMockPrivateChecks++
        if ($global:HysSmokeMockPublished) { return '[{"HostIp":"127.0.0.1","HostPort":"12345"}]' }
        return 'null'
    }
    throw 'Unexpected Docker invocation in synthetic mock'
}
function Assert-Rejected($Name, [scriptblock]$Action) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw "$Name was not rejected" }
}

& $script:SmokePath -BaseUrl 'https://localhost' | Out-Null
if ($global:HysSmokeMockPrivateChecks -ne 5) { throw 'All five DB/S3/AV private endpoints must be checked' }
$global:HysSmokeMockPublished = $true
Assert-Rejected 'Published private port' { & $script:SmokePath }
$global:HysSmokeMockPublished = $false
$global:HysSmokeMockMissingService = $true
Assert-Rejected 'Missing private service' { & $script:SmokePath }
$global:HysSmokeMockMissingService = $false
$global:HysSmokeMockMigrationExit = 1
Assert-Rejected 'Failed migration' { & $script:SmokePath }
$global:HysSmokeMockMigrationExit = 0
$global:HysSmokeMockBadHealth = $true
Assert-Rejected 'Unhealthy API' { & $script:SmokePath }
$global:HysSmokeMockBadHealth = $false
Assert-Rejected 'Remote TLS bypass' { & $script:SmokePath -BaseUrl 'https://remote.example.invalid' -AllowLocalCertificate }
$source = Get-Content $script:SmokePath -Raw
if ($source -notmatch 'PowerShell 7' -or $source -match 'ServerCertificateValidationCallback') {
    throw 'TLS bypass must explicitly require PowerShell 7 without global overrides'
}
Write-Output 'Smoke mock regressions OK: 7 cases, no live HTTP/Docker calls'

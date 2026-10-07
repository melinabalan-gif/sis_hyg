param(
    [string]$BaseUrl = "https://localhost",
    [switch]$AllowLocalCertificate
)

$ErrorActionPreference = "Stop"
$base = [Uri]$BaseUrl
if ($AllowLocalCertificate) {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "AllowLocalCertificate requires PowerShell 7. Run pwsh -File scripts/smoke.ps1 -AllowLocalCertificate or trust the local certificate and omit the switch."
    }
    if (-not $base.IsLoopback -or $base.Scheme -ne 'https') {
        throw "Certificate bypass is allowed only for explicit HTTPS loopback smoke."
    }
}
$params = @{ Uri = "$($BaseUrl.TrimEnd('/'))/api/v1/health/live"; UseBasicParsing = $true; TimeoutSec = 10; MaximumRedirection = 0 }
if ($AllowLocalCertificate) {
    $params.SkipCertificateCheck = $true
}
function Invoke-SmokeRequest {
    param([hashtable]$Parameters, [switch]$WebPage)
    for ($attempt = 0; $attempt -le 30; $attempt++) {
        try {
            if ($WebPage) { return Invoke-WebRequest @Parameters }
            return Invoke-RestMethod @Parameters
        } catch {
            if ($attempt -eq 30) { throw "Smoke HTTP request failed after bounded retries; response details withheld." }
            Start-Sleep -Seconds 2
        }
    }
}
$live = Invoke-SmokeRequest -Parameters $params
if ($live.status -ne "ok") { throw "Invalid liveness" }

$params.Uri = "$BaseUrl/api/v1/health/ready"
$ready = Invoke-SmokeRequest -Parameters $params
if ($ready.status -ne "ready") { throw "Invalid readiness" }

$params.Uri = "$BaseUrl/"
$homepage = Invoke-SmokeRequest -Parameters $params -WebPage
if ($homepage.Content -notmatch 'DATOS 100 % SINT\u00C9TICOS') {
    throw "Homepage does not show the synthetic marker"
}

$exited = @(docker compose ps --status exited --services migrate)
if ($LASTEXITCODE -ne 0 -or $exited -notcontains 'migrate') { throw "Migration did not exit successfully" }
$migrationJson = @(docker compose ps -a --format json migrate)
if ($LASTEXITCODE -ne 0 -or $migrationJson.Count -eq 0) { throw "Migration inspection unavailable" }
$migration = @($migrationJson | ForEach-Object { $_ | ConvertFrom-Json })
if ($migration.Count -eq 0 -or @($migration | Where-Object { $_.ExitCode -ne 0 }).Count -ne 0) {
    throw "Migration did not exit successfully"
}
foreach ($endpoint in @(@('db', '5432'), @('seaweedfs', '8333'), @('seaweedfs', '8888'), @('seaweedfs', '9333'), @('clamav', '3310'))) {
    $containers = @(docker compose ps -q $endpoint[0])
    if ($LASTEXITCODE -ne 0 -or $containers.Count -eq 0 -or [string]::IsNullOrWhiteSpace(($containers -join ''))) {
        throw "Private service inspection unavailable"
    }
    foreach ($container in $containers) {
        # Go raw-string quoting survives Windows PowerShell 5.1 native argv parsing.
        $template = '{{json (index .NetworkSettings.Ports `' + $endpoint[1] + '/tcp`)}}'
        $published = @(docker inspect --format $template $container)
        if ($LASTEXITCODE -ne 0) { throw "Private port inspection unavailable" }
        $bindings = ($published -join '').Trim()
        if ($bindings -notin @('null', '[]')) { throw "DB/S3/AV ports must not be published on the host or inspection is invalid" }
    }
}
Write-Output "Smoke OK"

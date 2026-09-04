param(
    [string]$BaseUrl = "https://localhost",
    [switch]$AllowLocalCertificate
)

$ErrorActionPreference = "Stop"
$params = @{ Uri = "$BaseUrl/api/v1/health/live"; UseBasicParsing = $true }
if ($AllowLocalCertificate -and $PSVersionTable.PSVersion.Major -ge 7) {
    $params.SkipCertificateCheck = $true
}
$live = Invoke-RestMethod @params
if ($live.status -ne "ok") { throw "Liveness inválido" }

$params.Uri = "$BaseUrl/api/v1/health/ready"
$ready = Invoke-RestMethod @params
if ($ready.status -ne "ready") { throw "Readiness inválido" }

$params.Uri = "$BaseUrl/"
$home = Invoke-WebRequest @params
if ($home.Content -notmatch "DATOS 100 % SINTÉTICOS") {
    throw "La portada no muestra el marcador sintético"
}

$migration = docker compose ps -a --format json migrate | ConvertFrom-Json
if ($migration.ExitCode -ne 0) { throw "El migrador no terminó correctamente" }
Write-Output "Smoke OK"


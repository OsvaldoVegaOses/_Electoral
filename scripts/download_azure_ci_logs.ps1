param(
    [Parameter(Mandatory=$true)][string]$Registry,
    [Parameter(Mandatory=$true)][string]$ResourceGroup,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$RunId,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$s3Root = Split-Path -Parent $PSScriptRoot
$s3Runtime = [IO.Path]::GetFullPath((Join-Path $s3Root '.runtime'))
$s3Output = [IO.Path]::GetFullPath((Join-Path $s3Root $Output))
if (-not $s3Output.StartsWith($s3Runtime + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Raw cloud logs must remain in the ignored .runtime directory.'
}
$s3RegistryId = az acr show --name $Registry --resource-group $ResourceGroup --query id -o tsv
if ($LASTEXITCODE -ne 0 -or -not $s3RegistryId) { throw 'Cannot resolve the authorized registry.' }
$s3LogUrl = "$s3RegistryId/runs/$RunId/listLogSasUrl?api-version=2019-04-01"
$s3Log = az rest --method post --url "https://management.azure.com$s3LogUrl" -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $s3Log.logLink) { throw 'Azure did not return a log link.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $s3Output) | Out-Null
try {
    Invoke-WebRequest -Uri $s3Log.logLink -OutFile $s3Output -UseBasicParsing -ErrorAction Stop
} catch {
    # Never echo the temporary SAS URL in a terminal, artifact or exception.
    throw ('Log download failed: ' + $_.Exception.GetType().Name)
}
[PSCustomObject]@{ runId=$RunId; logFile=$s3Output; sha256=(Get-FileHash -LiteralPath $s3Output -Algorithm SHA256).Hash.ToLowerInvariant() } | ConvertTo-Json

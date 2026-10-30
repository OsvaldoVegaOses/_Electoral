param([ValidateSet('run','status','preflight','pause','resume')][string]$Action='run')
$ErrorActionPreference='Stop'
$s3Repository=Split-Path -Parent $PSScriptRoot
$s3Interpreter=(Get-Command python.exe -ErrorAction Stop).Source
$s3Controller=Join-Path $s3Repository 'automation/sprint3/controller.py'
Set-Location -LiteralPath $s3Repository
& $s3Interpreter $s3Controller $Action
exit $LASTEXITCODE

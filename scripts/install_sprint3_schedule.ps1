param([ValidateRange(1,24)][int]$IntervalHours=3)
$ErrorActionPreference='Stop'
$s3Repository=Split-Path -Parent $PSScriptRoot
$s3Name='TheoGen-Electoral-Sprint3-Autonomous'
$s3Runner=Join-Path $PSScriptRoot 'run_sprint3_autonomous.ps1'
$s3PowerShell=(Get-Command powershell.exe -ErrorAction Stop).Source
$s3Identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$s3Arguments='-NoProfile -NonInteractive -WindowStyle Hidden -File "'+$s3Runner+'" -Action run'
$s3Action=New-ScheduledTaskAction -Execute $s3PowerShell -Argument $s3Arguments -WorkingDirectory $s3Repository
$s3Start=(Get-Date).AddHours($IntervalHours)
$s3Trigger=New-ScheduledTaskTrigger -Daily -At $s3Start
$s3Repetition=New-ScheduledTaskTrigger -Once -At $s3Start -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration (New-TimeSpan -Days 1)
$s3Trigger.Repetition=$s3Repetition.Repetition
$s3Settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$s3Principal=New-ScheduledTaskPrincipal -UserId $s3Identity -LogonType Interactive -RunLevel Limited
$s3Existing=Get-ScheduledTask -TaskName $s3Name -ErrorAction SilentlyContinue
if ($s3Existing -and (($s3Existing.Actions | Select-Object -First 1).Arguments -ne $s3Arguments)) {
    throw 'A different task already uses this name; preserve it and review before replacement.'
}
Register-ScheduledTask -TaskName $s3Name -Action $s3Action -Trigger $s3Trigger -Settings $s3Settings -Principal $s3Principal -Description 'Sprint 3: bounded isolated development, exact-SHA Azure CI and technical PR integration. No electoral approvals.' -Force | Out-Null
$s3Information=Get-ScheduledTaskInfo -TaskName $s3Name
[PSCustomObject]@{task=$s3Name;state=(Get-ScheduledTask -TaskName $s3Name).State.ToString();nextRun=$s3Information.NextRunTime.ToString('o');intervalHours=$IntervalHours;dailyAgentLimit=4;requiresLoggedInWindowsSession=$true} | ConvertTo-Json

$ErrorActionPreference = "Stop"

$python = "C:\Users\AIF\AppData\Local\Programs\Python\Python312\pythonw.exe"
$script = "C:\Users\AIF\obs-automation\obs_stream_ctl.py"
$obsExe = "C:\Program Files\obs-studio\bin\64bit\obs64.exe"
$obsDir = "C:\Program Files\obs-studio\bin\64bit"
$user = "$env:USERDOMAIN\$env:USERNAME"

function Register-OrReplace {
    param($Name, $Action, $Trigger)
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger `
        -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 10)) `
        -User $user -RunLevel Limited | Out-Null
    Write-Host "Registered: $Name"
}

# Launch OBS ahead of session 1 in case it's not already open
Register-OrReplace -Name "AIF Stream - Launch OBS" `
    -Action (New-ScheduledTaskAction -Execute $obsExe -WorkingDirectory $obsDir) `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "12:55PM")

# Session 1: 1:05pm - 2:00pm
Register-OrReplace -Name "AIF Stream - Session1 Start" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" start 1") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "1:05PM")

Register-OrReplace -Name "AIF Stream - Session1 Stop" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" stop") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "2:00PM")

# Session 2: 2:05pm - 3:00pm
Register-OrReplace -Name "AIF Stream - Session2 Start" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" start 2") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "2:05PM")

Register-OrReplace -Name "AIF Stream - Session2 Stop" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" stop") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "3:00PM")

Write-Host "`nAll tasks registered."

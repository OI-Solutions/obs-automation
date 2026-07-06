$ErrorActionPreference = "Stop"

$python = "C:\Users\AIF\AppData\Local\Programs\Python\Python312\pythonw.exe"
$reconcileScript = "C:\Users\AIF\obs-automation\reconcile.py"
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

# Launch OBS ahead of session 1 in case it's not already open. Guarded
# against OBS's own "already running" popup: if reconcile.py already
# launched OBS during a delayed-reboot catch-up, launching a second
# instance would pop a blocking dialog with nobody there to click it,
# which would take down every subsequent scheduled action silently.
Register-OrReplace -Name "AIF Stream - Launch OBS" `
    -Action (New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -WindowStyle Hidden -Command `"if (-not (Get-Process obs64 -ErrorAction SilentlyContinue)) { Start-Process -FilePath '$obsExe' -WorkingDirectory '$obsDir' }`"") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "12:55PM")

# Session 1: 1:05pm - 2:00pm. Session 2: 2:05pm - 3:00pm.
# All four fire the same idempotent reconcile.py instead of a hardcoded
# start/stop - see reconcile.py's module docstring and README's
# "Idempotent reconciliation" section for why.
Register-OrReplace -Name "AIF Stream - Session1 Start" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$reconcileScript`"") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "1:05PM")

Register-OrReplace -Name "AIF Stream - Session1 Stop" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$reconcileScript`"") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "2:00PM")

Register-OrReplace -Name "AIF Stream - Session2 Start" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$reconcileScript`"") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "2:05PM")

Register-OrReplace -Name "AIF Stream - Session2 Stop" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$reconcileScript`"") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "3:00PM")

# Self-heal immediately after a delayed reboot instead of waiting for the
# next fixed-time trigger to catch up hours later.
Register-OrReplace -Name "AIF Stream - Reconcile AtLogOn" `
    -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$reconcileScript`"") `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $user)

Write-Host "`nAll tasks registered."

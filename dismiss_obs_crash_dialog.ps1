# Dismisses OBS's "Crash Detected" recovery dialog without a mouse, by
# invoking its "Run in Normal Mode" button via UI Automation. SendKeys
# doesn't reliably reach this particular Qt dialog - this uses
# InvokePattern instead, which does.
#
# When you'd need this: OBS's last exit wasn't clean (force-killed rather
# than closed via CloseMainWindow()), so on next launch it blocks at this
# dialog instead of starting - which would otherwise hang forever on an
# unattended machine. See README.md Troubleshooting for more context.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty, "OBS Studio Crash Detected")
$dlg = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)

if ($null -eq $dlg) {
    Write-Output "No crash dialog found - nothing to do."
    exit 0
}

$buttonCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty, "Run in Normal Mode")
$btn = $dlg.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $buttonCond)

if ($null -eq $btn) {
    Write-Output "Dialog found but 'Run in Normal Mode' button not located - inspect manually."
    exit 1
}

$pattern = $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
$pattern.Invoke()
Write-Output "Dismissed crash dialog - OBS should now be starting normally."
